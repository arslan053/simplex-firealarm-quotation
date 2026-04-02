"""Add Uncategorized enum value and insert missing products

Revision ID: 026
Revises: 025
Create Date: 2026-03-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# fmt: off
_PRODUCTS = [
    ("2084-9009",      "PHONE ARMOR BREAK-ROD FLSH MNT",      276.20),
    ("2099-9138",      "PULL STAT CAST S/A B LOCK SPST",      33.09),
    ("4906-9106",      "WP MC VO NON-ADDR WALL WHITE",        48.31),
    ("4906-9107",      "ALERT MCVO NON-ADDR WALL WHT",        59.02),
    ("4906-9108",      "ALERT MCVO NON-ADDR WALL RED",        27.90),
    ("4906-9253",      "MC TRUEALERT S/V WALL MT WHITE",      65.54),
    ("49AO-APPLC",     "AUDIBLE APPLIANCE ONLY CEILING",      39.68),
    ("49AOC-CRFIRE",   "AO COVER, CEILING RED FIRE",          5.31),
    ("49CMT-WRF",      "CONVEN MT WALL RED FIRE",             36.36),
    ("49CMT-WWF",      "CONVEN MT WALL WHITE FIRE",           36.65),
    ("49CMTV-APPLW",   "CONVEN MTV APPLIANCE ONLY WALL",      56.58),
    ("49HF-APPLC",     "HIFI SPKR APPL ONLY CEILING",        67.14),
    ("49HF-APPLW",     "HIFI SPKR APPLIANC ONLY WALL",       54.57),
    ("49HFV-APPLC",    "HIFI SV APPLIANC ONLY CEILING",      101.66),
    ("49HFV-APPLW",    "HIFI SPKR/VIS APPL ONLY WALL",       81.39),
    ("49SO-APPLC",     "SPEAKER APPLIANCE ONLY CEILING",      70.92),
    ("49SO-APPLC-O",   "SO APPLIANCE ONLY CEILING WP",        110.06),
    ("49SOC-CRFIRE",   "COVER SPKR ONLY CEIL RED FIRE",       7.79),
    ("49SOC-CRFIRE-O", "SO COVER, CEILING RED FIRE WP",       9.49),
    ("49SOC-WRFIRE",   "SPKR COVER WALL RED FIRE",            5.91),
    ("49SOC-WRFIRE-O", "SO COVER,WALL,RED,FIRE WP",           9.49),
    ("49SVC-CRFIRE",   "SV COVER CEIL RED FIRE",              8.24),
    ("49SVC-WRFIRE",   "SV COVER WALL RED FIRE",              5.48),
    ("49SVC-WRFIRE-O", "SV COVER, WALL,RED,FIRE WP",          9.49),
    ("EL3RSPK-NW",     "N3R SPKR, WHT, WALL, BLNK",          138.80),
    ("EL3RSPST-FW",    "N3R SPKSTR, WHT, WALL, FIRE",         230.11),
    ("GBBB",           "GBSERIES BELL BACK BOX",              11.16),
    ("4190-6301",      "SMFO Card Left Port",                  1053.11),
    ("4190-6302",      "SMFO Card Left Port",                  1053.11),
    ("49AV-WWFO",      "WP ADDR AV WALL WHT FIRE BA",         99.00),
    ("49VO-WWFO",      "VO ONLY WHITE",                        48.68),
    ("49VOC-CRF",      "VO Cover",                             8.31),
    ("Surguard-V",     "Surguard With DACR feature",           12580.00),
    ("49CMTV-WWF",     "Multi Tone Horn Flasher White",        0),
]
# fmt: on


def upgrade() -> None:
    # 1. Add new enum value
    op.execute(
        "ALTER TYPE product_category_enum ADD VALUE IF NOT EXISTS 'Uncategorized'"
    )
    # Commit so the new enum value is visible within this transaction (asyncpg requirement)
    op.execute("COMMIT")

    # 2. Insert products (skip any that already exist)
    for code, description, price in _PRODUCTS:
        desc_safe = description.replace("'", "''")
        op.execute(
            f"INSERT INTO products (id, code, description, price, currency, category, created_at, updated_at) "
            f"VALUES (gen_random_uuid(), '{code}', '{desc_safe}', {price}, 'USD', 'Uncategorized', now(), now()) "
            f"ON CONFLICT (code) DO NOTHING"
        )


def downgrade() -> None:
    # Remove the inserted products
    codes = ", ".join(f"'{c}'" for c, _, _ in _PRODUCTS)
    op.execute(
        f"DELETE FROM products WHERE code IN ({codes}) AND category::text = 'Uncategorized'"
    )
    # Postgres cannot remove enum values; no-op for the enum
