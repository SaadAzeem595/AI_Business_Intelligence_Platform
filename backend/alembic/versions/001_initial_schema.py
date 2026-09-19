"""initial_production_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-19 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('clerk_user_id', sa.String(), unique=True, nullable=True),
        sa.Column('email', sa.String(), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('role', sa.String(), nullable=False, server_default='Viewer'),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_users_id', 'users', ['id'])
    op.create_index('ix_users_clerk_user_id', 'users', ['clerk_user_id'])
    op.create_index('ix_users_email', 'users', ['email'])

    # 2. projects table
    op.create_table(
        'projects',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('owner_id', sa.String(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='Active'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_projects_id', 'projects', ['id'])

    # 3. datasets table
    op.create_table(
        'datasets',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('size', sa.String(), nullable=False),
        sa.Column('rows', sa.Integer(), server_default='0'),
        sa.Column('qualityScore', sa.Integer(), server_default='0'),
        sa.Column('status', sa.String(), server_default='Active'),
        sa.Column('date', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=True),
        sa.Column('display_name', sa.String(), nullable=True),
        sa.Column('storage_path', sa.String(), nullable=True),
        sa.Column('duckdb_table', sa.String(), nullable=True),
        sa.Column('columns_json', sa.String(), nullable=True),
        sa.Column('schema_json', sa.String(), nullable=True),
        sa.Column('project_id', sa.String(), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True),
        sa.Column('owner_id', sa.String(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('original_filename', sa.String(), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_datasets_id', 'datasets', ['id'])

    # 4. reports table
    op.create_table(
        'reports',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('frequency', sa.String(), nullable=False),
        sa.Column('created', sa.String(), nullable=False),
        sa.Column('size', sa.String(), nullable=False),
        sa.Column('recipient', sa.String(), nullable=False),
        sa.Column('workspace', sa.String(), nullable=False, server_default='default'),
        sa.Column('project_id', sa.String(), nullable=True),
        sa.Column('author', sa.String(), nullable=False, server_default='system'),
        sa.Column('template', sa.String(), nullable=False, server_default='Executive Summary'),
        sa.Column('reporting_period', sa.String(), nullable=True, server_default='Last 30 Days'),
        sa.Column('data_sources', sa.String(), nullable=True),
        sa.Column('options', sa.String(), nullable=True),
        sa.Column('datasets_used', sa.String(), nullable=True),
        sa.Column('delivery_status', sa.String(), nullable=False, server_default='Pending'),
        sa.Column('delivery_error', sa.String(), nullable=True),
        sa.Column('file_path', sa.String(), nullable=True),
        sa.Column('report_data', sa.String(), nullable=True),
    )
    op.create_index('ix_reports_id', 'reports', ['id'])

    # 5. report_schedules table
    op.create_table(
        'report_schedules',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('workspace', sa.String(), nullable=False, server_default='default'),
        sa.Column('project_id', sa.String(), nullable=True),
        sa.Column('report_type', sa.String(), nullable=False),
        sa.Column('frequency', sa.String(), nullable=False),
        sa.Column('template', sa.String(), nullable=False, server_default='Executive Summary'),
        sa.Column('reporting_period', sa.String(), nullable=True, server_default='Last 30 Days'),
        sa.Column('data_sources', sa.String(), nullable=True),
        sa.Column('options', sa.String(), nullable=True),
        sa.Column('recipient', sa.String(), nullable=False),
        sa.Column('author', sa.String(), nullable=False, server_default='system'),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.String(), nullable=False),
    )
    op.create_index('ix_report_schedules_id', 'report_schedules', ['id'])

    # 6. workspace_subscriptions table
    op.create_table(
        'workspace_subscriptions',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('workspace_id', sa.String(), unique=True, nullable=False),
        sa.Column('stripe_customer_id', sa.String(), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(), nullable=True),
        sa.Column('stripe_price_id', sa.String(), nullable=True),
        sa.Column('plan', sa.String(), nullable=False, server_default='starter'),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('current_period_start', sa.DateTime(), nullable=True),
        sa.Column('current_period_end', sa.DateTime(), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_workspace_subscriptions_workspace_id', 'workspace_subscriptions', ['workspace_id'])
    op.create_index('ix_workspace_subscriptions_stripe_customer_id', 'workspace_subscriptions', ['stripe_customer_id'])
    op.create_index('ix_workspace_subscriptions_stripe_subscription_id', 'workspace_subscriptions', ['stripe_subscription_id'])

    # 7. stripe_processed_events table
    op.create_table(
        'stripe_processed_events',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('event_id', sa.String(), unique=True, nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='processed'),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_stripe_processed_events_event_id', 'stripe_processed_events', ['event_id'])
    op.create_index('ix_stripe_processed_events_workspace_id', 'stripe_processed_events', ['workspace_id'])


def downgrade() -> None:
    op.drop_table('stripe_processed_events')
    op.drop_table('workspace_subscriptions')
    op.drop_table('report_schedules')
    op.drop_table('reports')
    op.drop_table('datasets')
    op.drop_table('projects')
    op.drop_table('users')
