"""release parser v2 fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("release") as batch:
        batch.add_column(sa.Column("hdr", sa.Text, nullable=True))
        batch.add_column(sa.Column("cut", sa.Text, nullable=True))
        batch.add_column(sa.Column("ratio", sa.Text, nullable=True))
        batch.add_column(sa.Column("hybrid", sa.Boolean, nullable=True))
        batch.add_column(sa.Column("parser_version", sa.Integer, nullable=True))

    op.execute("UPDATE release SET parser_version = 1")


def downgrade() -> None:
    with op.batch_alter_table("release") as batch:
        batch.drop_column("parser_version")
        batch.drop_column("hybrid")
        batch.drop_column("ratio")
        batch.drop_column("cut")
        batch.drop_column("hdr")
