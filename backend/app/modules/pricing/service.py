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

    async def get_pricing(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> PricingResponse | None:
        project_name = await self._get_project_name(tenant_id, project_id)

        result = await self.db.execute(
            text("""
                SELECT id, section, row_number, description, quantity,
                       unit_cost_sar, total_sar, product_details, source_id
                FROM pricing_items
                WHERE tenant_id = :tid AND project_id = :pid
                ORDER BY section, row_number
            """),
            {"tid": tenant_id, "pid": project_id},
        )
        rows = result.fetchall()
        if not rows:
            return None

        items: list[PricingItem] = []
        for row in rows:
            details = row[7] if row[7] else []
            items.append(
                PricingItem(
                    id=str(row[0]),
                    section=row[1],
                    row_number=row[2],
                    description=row[3],
                    quantity=float(row[4]),
                    unit_cost_sar=float(row[5]),
                    total_sar=float(row[6]),
                    product_details=[
                        ProductDetail(code=d["code"], price_sar=d["price_sar"])
                        for d in details
                    ],
                )
            )

        device_subtotal = sum(i.total_sar for i in items if i.section == "device")
        panel_subtotal = sum(i.total_sar for i in items if i.section == "panel")

        return PricingResponse(
            project_id=str(project_id),
            project_name=project_name,
            calculated_at=items[0].id if items else "",
            usd_to_sar_rate=float(USD_TO_SAR),
            items=items,
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
        Fetch finalized device selections, join through selectable_products
        to get product prices. Group by selectable.
        """
        result = await self.db.execute(
            text("""
                SELECT
                    bds.selectable_id,
                    s.description AS selectable_description,
                    bi.quantity AS boq_quantity,
                    p.code AS product_code,
                    p.price AS product_price_usd
                FROM boq_device_selections bds
                JOIN boq_items bi ON bi.id = bds.boq_item_id
                JOIN selectables s ON s.id = bds.selectable_id
                JOIN selectable_products sp ON sp.selectable_id = bds.selectable_id
                JOIN products p ON p.id = sp.product_id
                WHERE bds.tenant_id = :tid
                  AND bds.project_id = :pid
                  AND bds.status = 'finalized'
                  AND bds.selectable_id IS NOT NULL
                ORDER BY s.description, p.code
            """),
            {"tid": tenant_id, "pid": project_id},
        )
        rows = result.fetchall()

        # Group by selectable_id
        groups: dict[str, dict] = {}
        for row in rows:
            sel_id = str(row[0])
            if sel_id not in groups:
                groups[sel_id] = {
                    "selectable_id": sel_id,
                    "description": row[1],
                    "quantity": float(row[2]) if row[2] else 1,
                    "products": {},
                }
            # Deduplicate products (same selectable may appear for multiple BOQ items)
            code = row[3]
            if code not in groups[sel_id]["products"]:
                price_usd = Decimal(str(row[4])) if row[4] else Decimal("0")
                price_sar = _round_sar(price_usd * USD_TO_SAR)
                groups[sel_id]["products"][code] = float(price_sar)

        items: list[PricingItem] = []
        row_num = 0
        for sel_id, group in groups.items():
            row_num += 1
            products = group["products"]
            unit_cost_sar = float(_round_sar(sum(Decimal(str(v)) for v in products.values())))
            quantity = group["quantity"]
            total_sar = float(_round_sar(Decimal(str(unit_cost_sar)) * Decimal(str(quantity))))

            items.append(
                PricingItem(
                    id=sel_id,
                    section="device",
                    row_number=row_num,
                    description=group["description"],
                    quantity=quantity,
                    unit_cost_sar=unit_cost_sar,
                    total_sar=total_sar,
                    product_details=[
                        ProductDetail(code=code, price_sar=price)
                        for code, price in products.items()
                    ],
                )
            )

        return items

    async def _build_panel_items(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> list[PricingItem]:
        """
        Fetch panel selections, join to products for prices.
        Multiply by panel_groups.quantity if grouped.
        """
        result = await self.db.execute(
            text("""
                SELECT
                    ps.id,
                    ps.product_code,
                    p.description AS product_description,
                    p.price AS product_price_usd,
                    ps.quantity AS ps_quantity,
                    pg.quantity AS group_quantity
                FROM panel_selections ps
                JOIN products p ON p.code = ps.product_code
                LEFT JOIN panel_groups pg ON pg.id = ps.panel_group_id
                WHERE ps.tenant_id = :tid
                  AND ps.project_id = :pid
                ORDER BY ps.product_code
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
            description = row[2]
            price_usd = Decimal(str(row[3])) if row[3] else Decimal("0")
            ps_quantity = int(row[4]) if row[4] else 1
            group_quantity = int(row[5]) if row[5] else 1

            unit_cost_sar = float(_round_sar(price_usd * USD_TO_SAR))
            total_quantity = ps_quantity * group_quantity
            total_sar = float(_round_sar(Decimal(str(unit_cost_sar)) * Decimal(str(total_quantity))))

            items.append(
                PricingItem(
                    id=ps_id,
                    section="panel",
                    row_number=row_num,
                    description=description,
                    quantity=total_quantity,
                    unit_cost_sar=unit_cost_sar,
                    total_sar=total_sar,
                    product_details=[
                        ProductDetail(code=product_code, price_sar=unit_cost_sar),
                    ],
                )
            )

        return items


def _product_details_json(details: list[ProductDetail]) -> str:
    import json
    return json.dumps([{"code": d.code, "price_sar": d.price_sar} for d in details])


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False
