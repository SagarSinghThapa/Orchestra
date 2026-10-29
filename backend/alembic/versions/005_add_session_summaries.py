"""add_session_summaries

Revision ID: 005_add_session_summaries
Revises: 004_add_checkpoints
Create Date: 2026-10-29 20:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_add_session_summaries'
down_revision: Union[str, Sequence[str], None] = '004_add_checkpoints'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create session_summaries table for persistent conversational memory."""
    op.create_table(
        'session_summaries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('summary_text', sa.Text(), nullable=False),
        sa.Column('message_watermark_id', sa.Integer(), nullable=False),
        sa.Column('message_count_summarized', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_session_summaries_session_id', 'session_summaries', ['session_id'], unique=True)
    op.create_index('ix_session_summaries_project_id', 'session_summaries', ['project_id'], unique=False)


def downgrade() -> None:
    """Drop session_summaries table and associated indexes."""
    op.drop_index('ix_session_summaries_project_id', table_name='session_summaries')
    op.drop_index('ix_session_summaries_session_id', table_name='session_summaries')
    op.drop_table('session_summaries')

