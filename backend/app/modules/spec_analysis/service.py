"""Spec analysis service — convert spec to Markdown + answer analysis questions."""

import base64
import json
import logging
import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analysis.models import AnalysisAnswer
from app.modules.boq.models import BoqItem
from app.modules.projects.models import Project
from app.modules.prompt_questions.models import PromptQuestion
from app.modules.spec.parser import parse_spec_markdown
from app.modules.spec.repository import SpecBlockRepository, SpecDocumentRepository
from app.modules.spec_analysis.prompts import (
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_NO_SPEC,
    build_user_prompt,
    build_user_prompt_no_spec,
)
from app.modules.spec_analysis.schemas import SpecAnalysisResult
from app.shared.openai_client import get_openai_client
from app.shared.pipeline_errors import (
    empty_boq_output_error,
    incomplete_ai_response_error,
    invalid_ai_response_error,
    is_storage_error,
    no_ai_text_error,
    normalize_openai_error,
    save_output_error,
    storage_read_error,
)
from app.shared.storage import get_file_bytes

logger = logging.getLogger(__name__)

class SpecAnalysisService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.spec_doc_repo = SpecDocumentRepository(db)
        self.spec_block_repo = SpecBlockRepository(db)

    async def run(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> SpecAnalysisResult:
        """Convert spec to markdown and answer analysis questions.

        Requires BOQ items to already be extracted (reads from DB).
        """

        # ── Check if spec exists (optional now) ──
        spec_doc = await self.spec_doc_repo.get_existing_spec(tenant_id, project_id)
        has_spec = spec_doc is not None

        # ── Guard: BOQ items must already exist ──
        boq_items_result = await self.db.execute(
            select(BoqItem)
            .where(
                BoqItem.tenant_id == tenant_id,
                BoqItem.project_id == project_id,
            )
            .order_by(BoqItem.row_number.asc())
        )
        boq_items = list(boq_items_result.scalars().all())
        if not boq_items:
            raise empty_boq_output_error()

        # ── Guard: Questions must exist ──
        # Only load Protocol_decision and Panel_selection questions.
        # 4007_panel_questions are handled by the panel selection service.
        result = await self.db.execute(
            select(PromptQuestion)
            .where(PromptQuestion.category.in_(["Protocol_decision", "Panel_selection"]))
            .order_by(PromptQuestion.question_no.asc())
        )
        questions = list(result.scalars().all())
        if not questions:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No prompt questions configured in the system.",
            )

        # ── Build BOQ JSON from DB ──
        boq_items_json_list = []
        for item in boq_items:
            boq_items_json_list.append({
                "row_number": item.row_number,
                "type": item.type,
                "description": item.description,
                "quantity": float(item.quantity) if item.quantity is not None else None,
                "unit": item.unit,
                "category": item.category,
                "dimensions": item.dimensions,
            })
        boq_items_json = json.dumps(boq_items_json_list, ensure_ascii=False)

        questions_text = "\n".join(
            f"Q{q.question_no} [{q.category}]: {q.question}" for q in questions
        )

        # ── Build GPT input depending on spec availability ──
        if has_spec:
            # Full path: spec PDF + BOQ JSON
            try:
                spec_bytes = get_file_bytes(spec_doc.object_key)
            except Exception as exc:
                if is_storage_error(exc):
                    raise storage_read_error("spec_analysis", exc) from exc
                raise
            spec_b64 = base64.standard_b64encode(spec_bytes).decode("ascii")

            content_parts: list[dict] = [
                {
                    "type": "input_file",
                    "filename": "specification.pdf",
                    "file_data": f"data:application/pdf;base64,{spec_b64}",
                },
            ]
            user_prompt = build_user_prompt(questions_text, boq_items_json)
            content_parts.append({"type": "input_text", "text": user_prompt})
            system_prompt = SYSTEM_PROMPT
        else:
            # No-spec path: BOQ-only question answering
            content_parts = [
                {"type": "input_text", "text": build_user_prompt_no_spec(questions_text, boq_items_json)},
            ]
            system_prompt = SYSTEM_PROMPT_NO_SPEC

        # ── GPT call ──
        logger.info(
            "Spec analysis: starting for project %s (has_spec=%s)",
            project_id, has_spec,
        )
        client = get_openai_client()
        try:
            response = await client.responses.create(
                model="gpt-5.2",
                instructions=system_prompt,
                input=[{"role": "user", "content": content_parts}],
            )
        except Exception as exc:
            raise normalize_openai_error("spec_analysis", exc) from exc

        raw_text = _extract_text(response)
        parsed = _parse_json(raw_text)

        if not isinstance(parsed, dict):
            raise invalid_ai_response_error("spec_analysis")
        for key in ("spec_markdown", "analysis_answers"):
            if key not in parsed:
                raise incomplete_ai_response_error("spec_analysis")

        logger.info(
            "Spec analysis complete: %d answers",
            len(parsed.get("analysis_answers", [])),
        )

        try:
            # ── Delete old analysis answers ──
            await self.db.execute(
                delete(AnalysisAnswer).where(
                    AnalysisAnswer.tenant_id == tenant_id,
                    AnalysisAnswer.project_id == project_id,
                )
            )
            await self.db.flush()

            # ── Store spec blocks (only when spec exists) ──
            spec_blocks: list = []
            if has_spec:
                # Re-verify the document still exists — the user may have uploaded
                # a new spec while the GPT call was running, which deletes the old one.
                current_doc = await self.spec_doc_repo.get_existing_spec(tenant_id, project_id)
                if current_doc is None or current_doc.id != spec_doc.id:
                    logger.warning(
                        "Spec document changed during analysis for project %s. "
                        "Using current document.",
                        project_id,
                    )
                    spec_doc = current_doc

                if spec_doc is not None:
                    await self.spec_block_repo.delete_by_document(spec_doc.id, tenant_id)
                    spec_markdown = parsed.get("spec_markdown", "")
                    spec_blocks = parse_spec_markdown(
                        spec_markdown, spec_doc.id, tenant_id,
                        start_page=1, end_page=1,
                    )
                    if spec_blocks:
                        await self.spec_block_repo.bulk_create(spec_blocks)

            # ── Store analysis answers ──
            question_map = {q.question_no: q for q in questions}
            answers_data = parsed.get("analysis_answers", [])
            if not isinstance(answers_data, list):
                raise invalid_ai_response_error("spec_analysis")
            answer_models: list[AnalysisAnswer] = []

            for item in answers_data:
                if not isinstance(item, dict):
                    continue

                q_no = item.get("question_no")
                question = question_map.get(q_no)
                if not question:
                    continue

                answer = str(item.get("answer", "No"))
                if answer not in ("Yes", "No"):
                    answer = "No"

                confidence = str(item.get("confidence", "Low"))
                if confidence not in ("High", "Medium", "Low"):
                    confidence = "Low"

                inferred = str(item.get("inferred_from", "Both"))
                if inferred not in ("BOQ", "Specs", "Both"):
                    inferred = "Both"

                supporting = item.get("supporting_points", [])
                if not isinstance(supporting, list):
                    supporting = [str(supporting)]

                answer_models.append(
                    AnalysisAnswer(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        question_id=question.id,
                        answer=answer,
                        confidence=confidence,
                        supporting_notes=json.dumps(supporting),
                        inferred_from=inferred,
                    )
                )

            if answer_models:
                self.db.add_all(answer_models)
                await self.db.flush()

            # ── Derive and store protocol on the project ──
            protocol = _derive_protocol(question_map, answers_data)
            if protocol:
                project_protocol_result = await self.db.execute(
                    select(Project.protocol).where(
                        Project.id == project_id,
                        Project.tenant_id == tenant_id,
                    )
                )
                existing_protocol = project_protocol_result.scalar_one_or_none()
                values = {"protocol_auto": protocol}
                if existing_protocol is None:
                    values["protocol"] = protocol

                await self.db.execute(
                    update(Project)
                    .where(Project.id == project_id, Project.tenant_id == tenant_id)
                    .values(**values)
                )
                await self.db.flush()
                if existing_protocol:
                    logger.info(
                        "Stored protocol_auto=%s; preserved explicit protocol=%s for project %s",
                        protocol, existing_protocol, project_id,
                    )
                else:
                    logger.info("Stored protocol=%s for project %s", protocol, project_id)
        except HTTPException:
            raise
        except Exception as exc:
            raise save_output_error("spec_analysis", exc) from exc

        return SpecAnalysisResult(
            project_id=project_id,
            status="success",
            message=(
                f"Analysis complete. {len(spec_blocks)} spec blocks parsed, "
                f"{len(answer_models)} questions answered."
            ),
            spec_blocks_count=len(spec_blocks),
            answers_count=len(answer_models),
        )


# ── Private helpers ──

def _extract_text(response) -> str:
    for item in response.output:
        if getattr(item, "type", None) == "message":
            for block in getattr(item, "content", []):
                if getattr(block, "type", None) == "output_text":
                    return block.text
    raise no_ai_text_error("spec_analysis")


def _derive_protocol(
    question_map: dict[int, "PromptQuestion"],
    answers_data: list[dict],
) -> str | None:
    """Derive MX/IDNET from Protocol_decision Q1, Q3, Q4 answers.

    Any 'Yes' → MX, all 'No' → IDNET, otherwise None.
    """
    protocol_answers: dict[int, str] = {}
    for item in answers_data:
        q_no = item.get("question_no")
        q = question_map.get(q_no)
        if q and q.category == "Protocol_decision" and q_no in (1, 3, 4):
            ans = str(item.get("answer", "No"))
            protocol_answers[q_no] = ans

    if not protocol_answers:
        return None
    if any(v == "Yes" for v in protocol_answers.values()):
        return "MX"
    if all(v == "No" for v in protocol_answers.values()):
        return "IDNET"
    return None


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse GPT JSON: %s\nRaw: %s", e, raw[:500])
        raise invalid_ai_response_error("spec_analysis")
