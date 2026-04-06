from __future__ import annotations

import asyncio
import subprocess
import tempfile
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.storage import delete_file, get_file_bytes, get_file_url, upload_file

from .generator import QuotationData, QuotationProduct, generate_quotation
from .schemas import GenerateQuotationRequest, QuotationDownloadResponse, QuotationResponse


class QuotationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        data: GenerateQuotationRequest,
    ) -> QuotationResponse:
        # 1. Fetch project info
        project = await self._get_project(tenant_id, project_id)

        # 2. Fetch pricing items (must exist)
        pricing_items = await self._get_pricing_items(tenant_id, project_id)
        if not pricing_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pricing has not been calculated for this project. Calculate pricing first.",
            )

        # 3. Apply margin and build product list
        margin_mult = Decimal(1) + Decimal(str(data.margin_percent)) / Decimal(100)
        products: list[QuotationProduct] = []
        subtotal = Decimal(0)

        for item in pricing_items:
            # Each pricing item may have multiple product_details
            # We flatten: one row per product in the quotation
            details = item["product_details"] or []
            qty = Decimal(str(item["quantity"]))

            if details:
                for d in details:
                    base_price = Decimal(str(d["price_sar"]))
                    unit_price = (base_price * margin_mult).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    total_price = (unit_price * qty).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    subtotal += total_price
                    products.append(QuotationProduct(
                        code=d["code"],
                        description=item["description"] or d["code"],
                        quantity=float(qty),
                        unit_price=float(unit_price),
                        total_price=float(total_price),
                    ))
            else:
                base_price = Decimal(str(item["unit_cost_sar"]))
                unit_price = (base_price * margin_mult).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                total_price = (unit_price * qty).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                subtotal += total_price
                products.append(QuotationProduct(
                    code="",
                    description=item["description"] or "Item",
                    quantity=float(qty),
                    unit_price=float(unit_price),
                    total_price=float(total_price),
                ))

        vat = (subtotal * Decimal("0.15")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        grand_total = subtotal + vat

        # 4. Generate reference number
        ref_number = await self._generate_ref_number(tenant_id, user_id, project_id)

        # 5. Build DOCX
        qdata = QuotationData(
            client_name=data.client_name,
            client_address=data.client_address,
            reference_number=ref_number,
            generation_date=date.today(),
            project_name=project["project_name"],
            service_option=data.service_option,
            payment_terms_text=data.payment_terms_text,
            products=products,
            subtotal=float(subtotal),
            vat=float(vat),
            grand_total=float(grand_total),
        )
        docx_bytes = generate_quotation(qdata)

        # 6. Check for existing quotation
        existing = await self._get_existing(tenant_id, project_id)

        # 7. Upload to MinIO
        file_name = f"Quotation_{ref_number.replace('/', '-')}.docx"
        file_uuid = str(uuid.uuid4())
        object_key = f"{tenant_id}/{project_id}/quotations/{file_uuid}_{file_name}"

        if existing:
            # Delete old file from MinIO
            try:
                delete_file(existing["object_key"])
            except Exception:
                pass  # Old file may already be gone

        upload_file(
            object_key,
            docx_bytes,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        now = datetime.now(timezone.utc)

        # 8. Upsert quotation record
        if existing:
            await self.db.execute(
                text("""
                    UPDATE quotations SET
                        generated_by_user_id = :uid,
                        client_name = :client_name,
                        client_address = :client_address,
                        service_option = :service_option,
                        margin_percent = :margin_percent,
                        payment_terms_text = :payment_terms_text,
                        reference_number = :reference_number,
                        subtotal_sar = :subtotal,
                        vat_sar = :vat,
                        grand_total_sar = :grand_total,
                        object_key = :object_key,
                        original_file_name = :file_name,
                        file_size = :file_size,
                        updated_at = :now
                    WHERE tenant_id = :tid AND project_id = :pid
                """),
                {
                    "uid": user_id, "client_name": data.client_name,
                    "client_address": data.client_address,
                    "service_option": data.service_option,
                    "margin_percent": data.margin_percent,
                    "payment_terms_text": data.payment_terms_text,
                    "reference_number": ref_number,
                    "subtotal": float(subtotal), "vat": float(vat),
                    "grand_total": float(grand_total),
                    "object_key": object_key, "file_name": file_name,
                    "file_size": len(docx_bytes), "now": now,
                    "tid": tenant_id, "pid": project_id,
                },
            )
            quotation_id = existing["id"]
        else:
            q_id = uuid.uuid4()
            await self.db.execute(
                text("""
                    INSERT INTO quotations (
                        id, tenant_id, project_id, generated_by_user_id,
                        client_name, client_address, service_option,
                        margin_percent, payment_terms_text, reference_number,
                        subtotal_sar, vat_sar, grand_total_sar,
                        object_key, original_file_name, file_size
                    ) VALUES (
                        :id, :tid, :pid, :uid,
                        :client_name, :client_address, :service_option,
                        :margin_percent, :payment_terms_text, :reference_number,
                        :subtotal, :vat, :grand_total,
                        :object_key, :file_name, :file_size
                    )
                """),
                {
                    "id": q_id, "tid": tenant_id, "pid": project_id, "uid": user_id,
                    "client_name": data.client_name,
                    "client_address": data.client_address,
                    "service_option": data.service_option,
                    "margin_percent": data.margin_percent,
                    "payment_terms_text": data.payment_terms_text,
                    "reference_number": ref_number,
                    "subtotal": float(subtotal), "vat": float(vat),
                    "grand_total": float(grand_total),
                    "object_key": object_key, "file_name": file_name,
                    "file_size": len(docx_bytes),
                },
            )
            quotation_id = q_id

        await self.db.commit()

        return QuotationResponse(
            id=str(quotation_id),
            project_id=str(project_id),
            reference_number=ref_number,
            client_name=data.client_name,
            client_address=data.client_address,
            service_option=data.service_option,
            margin_percent=data.margin_percent,
            payment_terms_text=data.payment_terms_text,
            subtotal_sar=float(subtotal),
            vat_sar=float(vat),
            grand_total_sar=float(grand_total),
            original_file_name=file_name,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
        )

    async def get_quotation(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID
    ) -> QuotationResponse | None:
        result = await self.db.execute(
            text("""
                SELECT id, reference_number, client_name, client_address,
                       service_option, margin_percent, payment_terms_text,
                       subtotal_sar, vat_sar, grand_total_sar,
                       original_file_name, created_at, updated_at
                FROM quotations
                WHERE tenant_id = :tid AND project_id = :pid
            """),
            {"tid": tenant_id, "pid": project_id},
        )
        row = result.fetchone()
        if not row:
            return None

        return QuotationResponse(
            id=str(row[0]),
            project_id=str(project_id),
            reference_number=row[1],
            client_name=row[2],
            client_address=row[3],
            service_option=row[4],
            margin_percent=float(row[5]),
            payment_terms_text=row[6],
            subtotal_sar=float(row[7]),
            vat_sar=float(row[8]),
            grand_total_sar=float(row[9]),
            original_file_name=row[10],
            created_at=row[11].isoformat() if row[11] else "",
            updated_at=row[12].isoformat() if row[12] else "",
        )

    async def get_download_url(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID
    ) -> QuotationDownloadResponse | None:
        result = await self.db.execute(
            text("""
                SELECT object_key, original_file_name
                FROM quotations
                WHERE tenant_id = :tid AND project_id = :pid
            """),
            {"tid": tenant_id, "pid": project_id},
        )
        row = result.fetchone()
        if not row:
            return None

        url = get_file_url(row[0])
        return QuotationDownloadResponse(url=url, file_name=row[1])

    async def get_preview_pdf(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID
    ) -> bytes | None:
        """Download the DOCX from MinIO, convert to PDF via LibreOffice, return bytes."""
        result = await self.db.execute(
            text("""
                SELECT object_key FROM quotations
                WHERE tenant_id = :tid AND project_id = :pid
            """),
            {"tid": tenant_id, "pid": project_id},
        )
        row = result.fetchone()
        if not row:
            return None

        docx_bytes = get_file_bytes(row[0])

        # Convert DOCX → PDF using LibreOffice in a temp directory
        pdf_bytes = await asyncio.to_thread(self._convert_docx_to_pdf, docx_bytes)
        return pdf_bytes

    @staticmethod
    def _convert_docx_to_pdf(docx_bytes: bytes) -> bytes:
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = Path(tmpdir) / "quotation.docx"
            docx_path.write_bytes(docx_bytes)

            subprocess.run(
                [
                    "soffice", "--headless", "--convert-to", "pdf",
                    "--outdir", tmpdir, str(docx_path),
                ],
                check=True,
                capture_output=True,
                timeout=30,
            )

            pdf_path = Path(tmpdir) / "quotation.pdf"
            return pdf_path.read_bytes()

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    async def _get_project(self, tenant_id: uuid.UUID, project_id: uuid.UUID) -> dict:
        result = await self.db.execute(
            text("""
                SELECT project_name, client_name, city
                FROM projects
                WHERE id = :pid AND tenant_id = :tid
            """),
            {"tid": tenant_id, "pid": project_id},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found."
            )
        return {"project_name": row[0], "client_name": row[1], "city": row[2]}

    async def _get_pricing_items(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID
    ) -> list[dict]:
        result = await self.db.execute(
            text("""
                SELECT description, quantity, unit_cost_sar, total_sar, product_details
                FROM pricing_items
                WHERE tenant_id = :tid AND project_id = :pid
                ORDER BY section, row_number
            """),
            {"tid": tenant_id, "pid": project_id},
        )
        rows = result.fetchall()
        return [
            {
                "description": r[0],
                "quantity": float(r[1]),
                "unit_cost_sar": float(r[2]),
                "total_sar": float(r[3]),
                "product_details": r[4] if r[4] else [],
            }
            for r in rows
        ]

    async def _get_existing(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID
    ) -> dict | None:
        result = await self.db.execute(
            text("""
                SELECT id, object_key FROM quotations
                WHERE tenant_id = :tid AND project_id = :pid
            """),
            {"tid": tenant_id, "pid": project_id},
        )
        row = result.fetchone()
        if not row:
            return None
        return {"id": row[0], "object_key": row[1]}

    async def _generate_ref_number(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> str:
        # Count user's projects for sequence number
        result = await self.db.execute(
            text("""
                SELECT COUNT(*) FROM projects
                WHERE owner_user_id = :uid AND tenant_id = :tid
                  AND created_at <= (SELECT created_at FROM projects WHERE id = :pid)
            """),
            {"uid": user_id, "tid": tenant_id, "pid": project_id},
        )
        seq = result.scalar() or 1

        year = date.today().year

        return f"{seq}/{year}"
