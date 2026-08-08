"""Add OAuth fields and make hashed_password nullable.

Revision ID: a1b2c3d4e5f6
Revises: 2dd0e2e0757f
Create Date: 2026-07-27 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "2dd0e2e0757f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "hashed_password",
            existing_type=sa.String(length=255),
            nullable=True,
        )
        batch_op.add_column(sa.Column("oauth_provider", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("oauth_sub", sa.String(length=255), nullable=True))
        batch_op.create_index(batch_op.f("ix_users_oauth_sub"), ["oauth_sub"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_oauth_sub"))
        batch_op.drop_column("oauth_sub")
        batch_op.drop_column("oauth_provider")
        batch_op.alter_column(
            "hashed_password",
            existing_type=sa.String(length=255),
            nullable=False,
        )
