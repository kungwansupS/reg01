"""Add file_registry table for vector metadata tracking

Revision ID: 002
Revises: 001
Create Date: 2026-02-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "file_registry",
        sa.Column("file_path", sa.String(), primary_key=True),
        sa.Column("file_hash", sa.String(), nullable=False),
        sa.Column(
            "last_updated",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_file_registry_last_updated", "file_registry", ["last_updated"])


def downgrade() -> None:
    op.drop_index("idx_file_registry_last_updated", table_name="file_registry")
    op.drop_table("file_registry")
