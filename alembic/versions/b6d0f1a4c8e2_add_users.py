"""Add users for frontend authentication.

Revision ID: b6d0f1a4c8e2
Revises: 63034c35fb4f
"""

from alembic import op
import sqlalchemy as sa


revision = "b6d0f1a4c8e2"
down_revision = "63034c35fb4f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
