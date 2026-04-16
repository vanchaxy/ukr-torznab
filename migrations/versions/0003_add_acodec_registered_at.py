"""add acodec and registered_at to release

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-16 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EPOCH = "1970-01-01 00:00:00+00:00"


def upgrade() -> None:
    with op.batch_alter_table("release") as batch:
        batch.add_column(sa.Column("acodec", sa.Text, nullable=True))
        batch.add_column(
            sa.Column(
                "registered_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=_EPOCH,
            )
        )

    op.execute(f"UPDATE release SET registered_at = '{_EPOCH}'")


def downgrade() -> None:
    with op.batch_alter_table("release") as batch:
        batch.drop_column("registered_at")
        batch.drop_column("acodec")
