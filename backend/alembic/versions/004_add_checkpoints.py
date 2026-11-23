"""add_checkpoints

Revision ID: 004_add_checkpoints
Revises: 003_add_documents
Create Date: 2026-10-29 01:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_add_checkpoints'
down_revision: Union[str, Sequence[str], None] = '003_add_documents'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create checkpoints and checkpoint_writes tables for LangGraph state persistence."""
    op.create_table(
        'checkpoints',
        sa.Column('thread_id', sa.String(length=255), nullable=False),
        sa.Column('checkpoint_ns', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('checkpoint_id', sa.String(length=255), nullable=False),
        sa.Column('parent_checkpoint_id', sa.String(length=255), nullable=True),
        sa.Column('type', sa.String(length=100), nullable=True),
        sa.Column('checkpoint', sa.Text(), nullable=False),
        sa.Column('metadata', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('thread_id', 'checkpoint_ns', 'checkpoint_id', name='pk_checkpoints')
    )
    op.create_index(op.f('ix_checkpoints_thread_id'), 'checkpoints', ['thread_id'], unique=False)
    op.create_index(op.f('ix_checkpoints_created_at'), 'checkpoints', ['created_at'], unique=False)

    op.create_table(
        'checkpoint_writes',
        sa.Column('thread_id', sa.String(length=255), nullable=False),
        sa.Column('checkpoint_ns', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('checkpoint_id', sa.String(length=255), nullable=False),
        sa.Column('task_id', sa.String(length=255), nullable=False),
        sa.Column('idx', sa.Integer(), nullable=False),
        sa.Column('channel', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=100), nullable=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('thread_id', 'checkpoint_ns', 'checkpoint_id', 'task_id', 'idx', name='pk_checkpoint_writes')
    )
    op.create_index(op.f('ix_checkpoint_writes_thread_id'), 'checkpoint_writes', ['thread_id'], unique=False)


def downgrade() -> None:
    """Drop checkpoint_writes and checkpoints tables."""
    op.drop_table('checkpoint_writes')
    op.drop_table('checkpoints')
