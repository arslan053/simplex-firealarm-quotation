"""Replace payment percentage columns with payment_terms_text

Drops advance_percent, delivery_percent, completion_percent and adds
payment_terms_text (TEXT). The frontend now always sends the full
payment terms text, making the individual percentage columns redundant.

Revision ID: 032
Revises: 031
Create Date: 2026-04-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "032"
down_revision: Union[str, None] = "031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("quotations", sa.Column("payment_terms_text", sa.Text(), nullable=True))
    op.drop_column("quotations", "advance_percent")
    op.drop_column("quotations", "delivery_percent")
    op.drop_column("quotations", "completion_percent")


def downgrade() -> None:
    op.add_column("quotations", sa.Column("completion_percent", sa.Numeric(5, 2), nullable=False, server_default="5.00"))
    op.add_column("quotations", sa.Column("delivery_percent", sa.Numeric(5, 2), nullable=False, server_default="70.00"))
    op.add_column("quotations", sa.Column("advance_percent", sa.Numeric(5, 2), nullable=False, server_default="25.00"))
    op.drop_column("quotations", "payment_terms_text")
