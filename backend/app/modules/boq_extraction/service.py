"""BOQ extraction service — extract BOQ items and label categories."""

import base64
import json
import logging
import re
import uuid
from collections import Counter

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.boq.models import BoqItem
from app.modules.boq.repository import BoqItemRepository, DocumentRepository
from app.modules.boq_extraction.prompts import SYSTEM_PROMPT, USER_PROMPT
from app.modules.boq_extraction.schemas import BoqExtractionResult
from app.modules.spec.repository import SpecDocumentRepository
from app.shared.openai_client import get_openai_client
from app.shared.storage import get_file_bytes

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {
    "detection_devices",
    "notification",
    "audio_panel",
    "special_items",
    "pc_tsw",
    "mimic_panel",
    "panel",
    "sub_panel",
    "remote_annunciator",
    "repeater",
}

_BOQ_MIME_MAP = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
}


class BoqExtractionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.doc_repo = DocumentRepository(db)
        self.boq_repo = BoqItemRepository(db)
        self.spec_doc_repo = SpecDocumentRepository(db)

    async def run(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> BoqExtractionResult:
        """Extract BOQ items and label categories. Spec is optional."""

        # ── Guard: BOQ doc must exist ──
        boq_docs = await self.doc_repo.get_by_project(tenant_id, project_id)
        if not boq_docs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No BOQ document found. Upload a BOQ file first.",
            )

        boq_doc = boq_docs[0]
        boq_bytes = get_file_bytes(boq_doc.object_key)

        boq_filename = boq_doc.original_file_name or "boq.pdf"
        boq_ext = boq_filename.rsplit(".", 1)[-1].lower()
        boq_mime = _BOQ_MIME_MAP.get(boq_ext, "application/pdf")
        boq_b64 = base64.standard_b64encode(boq_bytes).decode("ascii")

        # ── Build input: BOQ file + optional spec ──
        content_parts: list[dict] = [
            {
                "type": "input_file",
                "filename": boq_filename,
                "file_data": f"data:{boq_mime};base64,{boq_b64}",
            },
        ]

        spec_doc = await self.spec_doc_repo.get_existing_spec(tenant_id, project_id)
        if spec_doc:
            spec_bytes = get_file_bytes(spec_doc.object_key)
            spec_b64 = base64.standard_b64encode(spec_bytes).decode("ascii")
            content_parts.append({
                "type": "input_file",
                "filename": "specification.pdf",
                "file_data": f"data:application/pdf;base64,{spec_b64}",
            })

        content_parts.append({"type": "input_text", "text": USER_PROMPT})

        # ── GPT call ──
        logger.info("BOQ extraction: starting for project %s", project_id)
        client = get_openai_client()
        response = await client.responses.create(
            model="gpt-5.2",
            instructions=SYSTEM_PROMPT,
            input=[{"role": "user", "content": content_parts}],
        )

        raw_text = _extract_text(response)
        parsed = _parse_json(raw_text)

        if not isinstance(parsed, dict) or "boq_items" not in parsed:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="BOQ extraction: AI response missing required key: boq_items",
            )

        boq_items_data = parsed["boq_items"]
        logger.info("BOQ extraction complete: %d items", len(boq_items_data))

        # ── Delete old BOQ items ──
        for doc in boq_docs:
            await self.boq_repo.delete_by_document_id(doc.id, tenant_id)

        # ── Store new BOQ items ──
        boq_models = []
        for item_data in boq_items_data:
            row_type = str(item_data.get("type", "boq_item"))
            if row_type not in ("boq_item", "description", "section_description"):
                row_type = "boq_item"
            category = item_data.get("category")
            if category and category not in VALID_CATEGORIES:
                category = "special_items"
            if row_type in ("description", "section_description"):
                category = None

            quantity = item_data.get("quantity")
            if row_type in ("description", "section_description"):
                is_valid = True
            elif row_type == "boq_item" and item_data.get("description"):
                is_valid = True
            else:
                is_valid = False

            boq_models.append(
                BoqItem(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    document_id=boq_doc.id,
                    row_number=item_data.get("row_number", 0),
                    description=item_data.get("description"),
                    quantity=quantity,
                    unit=item_data.get("unit"),
                    is_hidden=False,
                    is_valid=is_valid,
                    type=row_type,
                    category=category,
                    dimensions=_parse_dimensions(item_data, row_type),
                )
            )

        if boq_models:
            await self.boq_repo.bulk_create(boq_models)

        # ── Compute document dominant category ──
        categorized = [m for m in boq_models if m.type == "boq_item" and m.category]
        if categorized:
            cats = [m.category for m in categorized]
            counter = Counter(cats)
            dominant, count = counter.most_common(1)[0]
            confidence = round(count / len(cats), 4)
            await self.doc_repo.update_document_category(
                boq_doc.id, tenant_id, dominant, confidence,
            )

        return BoqExtractionResult(
            project_id=project_id,
            status="success",
            message=f"BOQ extraction complete. {len(boq_models)} items extracted.",
            boq_items_count=len(boq_models),
        )


# ── Private helpers ──

def _extract_text(response) -> str:
    for item in response.output:
        if getattr(item, "type", None) == "message":
            for block in getattr(item, "content", []):
                if getattr(block, "type", None) == "output_text":
                    return block.text
    raise RuntimeError("GPT-5.2 did not return a text response")


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse GPT JSON: %s\nRaw: %s", e, raw[:500])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI returned an invalid response. Please try again.",
        )


def _parse_dimensions(item_data: dict, row_type: str) -> list | None:
    if row_type in ("description", "section_description"):
        return None
    dims = item_data.get("dimensions")
    if not dims or not isinstance(dims, list):
        return None
    validated = []
    for entry in dims:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not name:
            continue
        validated.append({
            "name": name,
            "quantity": entry.get("quantity"),
            "building_count": entry.get("building_count"),
        })
    return validated if validated else None
