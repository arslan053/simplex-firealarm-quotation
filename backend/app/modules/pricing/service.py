from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import PricingItem, PricingResponse, ProductDetail

USD_TO_SAR = Decimal("3.75")


def _round_sar(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class PricingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> PricingResponse:
        # 1. Get project name
        project_name = await self._get_project_name(tenant_id, project_id)

        # 2. Delete existing pricing items (idempotent)
        await self.db.execute(
            text(
                "DELETE FROM pricing_items "
                "WHERE tenant_id = :tid AND project_id = :pid"
            ),
            {"tid": tenant_id, "pid": project_id},
        )

        # 3. Fetch device selection pricing rows
        device_items = await self._build_device_items(tenant_id, project_id)

        # 4. Fetch panel selection pricing rows
        panel_items = await self._build_panel_items(tenant_id, project_id)

        # 5. Bulk insert all pricing items
        all_items = device_items + panel_items
        for item in all_items:
            await self.db.execute(
                text("""
                    INSERT INTO pricing_items
                        (tenant_id, project_id, section, row_number,
                         description, quantity, unit_cost_sar, total_sar,
                         product_details, source_id)
                    VALUES
                        (:tid, :pid, :section, :row_number,
                         :description, :quantity, :unit_cost_sar, :total_sar,
                         CAST(:product_details AS jsonb), :source_id)
                """),
                {
                    "tid": tenant_id,
                    "pid": project_id,
                    "section": item.section,
                    "row_number": item.row_number,
                    "description": item.description,
                    "quantity": item.quantity,
                    "unit_cost_sar": item.unit_cost_sar,
                    "total_sar": item.total_sar,
                    "product_details": _product_details_json(item.product_details),
                    "source_id": item.id if _is_uuid(item.id) else None,
                },
            )

        # 6. Build response
        device_subtotal = float(sum(Decimal(str(i.total_sar)) for i in device_items))
        panel_subtotal = float(sum(Decimal(str(i.total_sar)) for i in panel_items))

        return PricingResponse(
            project_id=str(project_id),
            project_name=project_name,
            calculated_at=datetime.now(timezone.utc).isoformat(),
            usd_to_sar_rate=float(USD_TO_SAR),
            items=all_items,
            device_subtotal=device_subtotal,
            panel_subtotal=panel_subtotal,
            subtotal=device_subtotal + panel_subtotal,
        )

    async def _get_project_name(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID
    ) -> str:
        result = await self.db.execute(
            text(
                "SELECT project_name FROM projects "
                "WHERE id = :pid AND tenant_id = :tid"
            ),
            {"tid": tenant_id, "pid": project_id},
        )
        row = result.fetchone()
        if not row:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )
        return row[0]

    async def _build_device_items(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> list[PricingItem]:
        """
        Fetch finalized device selections keyed by bds.id (one row per BOQ item).
        Uses BOQ item description, LEFT JOINs products to detect missing ones.
        """
        result = await self.db.execute(
            text("""
                SELECT
                    bds.id AS bds_id,
                    bi.description AS boq_description,
                    bi.quantity AS boq_quantity,
                    p.code AS product_code,
                    COALESCE(tpp.price, p.price, 0) AS product_price_usd
                FROM boq_device_selections bds
                JOIN boq_items bi ON bi.id = bds.boq_item_id
                JOIN selectable_products sp ON sp.selectable_id = bds.selectable_id
                LEFT JOIN products p ON p.id = sp.product_id
                LEFT JOIN tenant_product_prices tpp
                    ON tpp.product_id = p.id AND tpp.tenant_id = bds.tenant_id
                WHERE bds.tenant_id = :tid
                  AND bds.project_id = :pid
                  AND bds.status = 'finalized'
                  AND bds.selectable_id IS NOT NULL
                ORDER BY bds.created_at
            """),
            {"tid": tenant_id, "pid": project_id},
        )
        rows = result.fetchall()

        # Group by bds.id — each BOQ item becomes its own pricing row
        groups: dict[str, dict] = {}
        for row in rows:
            bds_id = str(row[0])
            if bds_id not in groups:
                groups[bds_id] = {
                    "bds_id": bds_id,
                    "description": row[1],
                    "quantity": float(row[2]) if row[2] else 1,
                    "products": {},
                }
            code = row[3]
            if code and code not in groups[bds_id]["products"]:
                price_usd = Decimal(str(row[4])) if row[4] else Decimal("0")
                price_sar = _round_sar(price_usd * USD_TO_SAR)
                missing = row[4] is None
                groups[bds_id]["products"][code] = {
                    "price_sar": float(price_sar),
                    "missing": missing,
                }

        items: list[PricingItem] = []
        row_num = 0
        for bds_id, group in groups.items():
            row_num += 1
            products = group["products"]
            unit_cost_sar = float(
                _round_sar(sum(Decimal(str(v["price_sar"])) for v in products.values()))
            )
            quantity = group["quantity"]
            total_sar = float(
                _round_sar(Decimal(str(unit_cost_sar)) * Decimal(str(quantity)))
            )

            product_details = [
                ProductDetail(code=code, price_sar=info["price_sar"], missing=info["missing"])
                for code, info in products.items()
            ]
            missing_products = [d.code for d in product_details if d.missing]

            items.append(
                PricingItem(
                    id=bds_id,
                    section="device",
                    row_number=row_num,
                    description=group["description"],
                    quantity=quantity,
                    unit_cost_sar=unit_cost_sar,
                    total_sar=total_sar,
                    product_details=product_details,
                    missing_products=missing_products,
                )
            )

        return items

    async def _build_panel_items(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> list[PricingItem]:
        """
        Fetch panel selections, LEFT JOIN to products for prices.
        Missing products (code='NONE' or not in DB) appear with price 0 and missing flag.
        Quantity is used as-is (already pre-multiplied by panel selection service).
        """
        result = await self.db.execute(
            text("""
                SELECT
                    ps.id,
                    ps.product_code,
                    p.description AS product_description,
                    COALESCE(tpp.price, p.price, 0) AS product_price_usd,
                    ps.quantity AS ps_quantity
                FROM panel_selections ps
                LEFT JOIN products p ON p.code = ps.product_code
                LEFT JOIN tenant_product_prices tpp
                    ON tpp.product_id = p.id AND tpp.tenant_id = ps.tenant_id
                WHERE ps.tenant_id = :tid
                  AND ps.project_id = :pid
                ORDER BY ps.created_at
            """),
            {"tid": tenant_id, "pid": project_id},
        )
        rows = result.fetchall()

        items: list[PricingItem] = []
        row_num = 0
        for row in rows:
            row_num += 1
            ps_id = str(row[0])
            product_code = row[1]
            product_description = row[2]
            price_usd_raw = row[3]
            quantity = int(row[4]) if row[4] else 1

            missing = product_description is None  # product not found in DB
            if missing:
                description = product_code  # fallback to the code itself
                price_usd = Decimal("0")
            else:
                description = product_description
                price_usd = Decimal(str(price_usd_raw)) if price_usd_raw else Decimal("0")

            unit_cost_sar = float(_round_sar(price_usd * USD_TO_SAR))
            total_sar = float(_round_sar(Decimal(str(unit_cost_sar)) * Decimal(str(quantity))))

            product_detail = ProductDetail(
                code=product_code, price_sar=unit_cost_sar, missing=missing,
            )
            missing_products = [product_code] if missing else []

            items.append(
                PricingItem(
                    id=ps_id,
                    section="panel",
                    row_number=row_num,
                    description=description,
                    quantity=quantity,
                    unit_cost_sar=unit_cost_sar,
                    total_sar=total_sar,
                    product_details=[product_detail],
                    missing_products=missing_products,
                )
            )

        return items


def _product_details_json(details: list[ProductDetail]) -> str:
    import json
    return json.dumps([
        {"code": d.code, "price_sar": d.price_sar, "missing": d.missing}
        for d in details
    ])


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False
