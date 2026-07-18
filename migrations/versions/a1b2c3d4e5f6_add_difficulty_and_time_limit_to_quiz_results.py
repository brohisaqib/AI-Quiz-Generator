"""add difficulty and time_limit_minutes to quiz_results

Revision ID: a1b2c3d4e5f6
Revises: 7f100e352036
Create Date: 2026-07-18 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '7f100e352036'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('quiz_results', sa.Column('difficulty', sa.String(length=50), nullable=True, server_default='Intermediate'))
    op.add_column('quiz_results', sa.Column('time_limit_minutes', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('quiz_results', 'time_limit_minutes')
    op.drop_column('quiz_results', 'difficulty')
