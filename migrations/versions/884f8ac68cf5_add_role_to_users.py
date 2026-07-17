"""add role to users

Revision ID: 884f8ac68cf5
Revises: 784f8ac68cf4
Create Date: 2026-07-16 11:45:32.332696

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '884f8ac68cf5'
down_revision = '784f8ac68cf4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('role', sa.String(length=50), nullable=False, server_default='user'))


def downgrade():
    op.drop_column('users', 'role')
