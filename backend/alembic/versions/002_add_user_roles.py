"""add_user_roles
 
Revision ID: 002_user_roles
Revises: 001_initial
Create Date: 2026-10-25 12:40:00.000000
 
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_user_roles'
down_revision: Union[str, Sequence[str], None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add role column to users table with server default 'member'."""
    op.add_column(
        'users',
        sa.Column('role', sa.String(length=20), nullable=False, server_default='member')
    )


def downgrade() -> None:
    """Drop role column from users table."""
    op.drop_column('users', 'role')
