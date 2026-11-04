"""Hide deleted templates while retaining referenced page snapshots.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision='0003'
down_revision='0002'
branch_labels=None
depends_on=None

def upgrade():
    connection=op.get_bind()
    existing={c['name'] for c in sa.inspect(connection).get_columns('templates')}
    if 'is_deleted' not in existing:
        op.add_column('templates',sa.Column('is_deleted',sa.Boolean(),nullable=False,server_default=sa.false()))

def downgrade():
    # Retain this flag to avoid accidentally exposing removed template records.
    pass
