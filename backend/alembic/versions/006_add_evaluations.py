"""add_evaluations

Revision ID: 006_add_evaluations
Revises: 005_add_session_summaries
Create Date: 2026-10-30 16:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_add_evaluations'
down_revision: Union[str, Sequence[str], None] = '005_add_session_summaries'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create evaluation_runs and evaluation_case_results tables."""
    op.create_table(
        'evaluation_runs',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('suite_id', sa.String(64), nullable=False),
        sa.Column('dataset_id', sa.String(64), nullable=False),
        sa.Column('dataset_version', sa.String(32), nullable=False),
        sa.Column('dataset_sha256', sa.String(64), nullable=False),
        sa.Column('execution_mode', sa.String(20), server_default='regression', nullable=False),
        sa.Column('model_name', sa.String(64), server_default='deterministic-test-provider', nullable=False),
        sa.Column('metric_schema_version', sa.String(16), server_default='1.0.0', nullable=False),
        sa.Column('target_type', sa.String(32), nullable=False),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('is_baseline', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('total_cases', sa.Integer(), server_default='0', nullable=False),
        sa.Column('passed_cases', sa.Integer(), server_default='0', nullable=False),
        sa.Column('failed_cases', sa.Integer(), server_default='0', nullable=False),
        sa.Column('duration_ms', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('summary_metrics', sa.JSON(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_evaluation_runs_id', 'evaluation_runs', ['id'])
    op.create_index('ix_evaluation_runs_project_id', 'evaluation_runs', ['project_id'])
    op.create_index('ix_evaluation_runs_created_by_user_id', 'evaluation_runs', ['created_by_user_id'])
    op.create_index('ix_evaluation_runs_suite_id', 'evaluation_runs', ['suite_id'])
    op.create_index('ix_evaluation_runs_status', 'evaluation_runs', ['status'])
    op.create_index('ix_evaluation_runs_is_baseline', 'evaluation_runs', ['is_baseline'])
    op.create_index(
        'ix_eval_runs_baseline_lookup',
        'evaluation_runs',
        ['suite_id', 'dataset_id', 'dataset_version', 'execution_mode'],
    )

    op.create_table(
        'evaluation_case_results',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True, nullable=False),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('evaluation_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('case_id', sa.String(64), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('duration_ms', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('metrics', sa.JSON(), nullable=False),
        sa.Column('failure_reason', sa.String(64), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
    )
    op.create_index('ix_evaluation_case_results_id', 'evaluation_case_results', ['id'])
    op.create_index('ix_evaluation_case_results_run_id', 'evaluation_case_results', ['run_id'])
    op.create_index('ix_evaluation_case_results_case_id', 'evaluation_case_results', ['case_id'])


def downgrade() -> None:
    """Drop evaluation_runs and evaluation_case_results tables."""
    op.drop_table('evaluation_case_results')
    op.drop_table('evaluation_runs')
