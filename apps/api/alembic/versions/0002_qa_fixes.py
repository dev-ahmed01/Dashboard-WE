"""Protect sessions, draft revisions and publication SEO snapshots.

Revision ID: 0002
Revises: 0001

0001 deliberately uses metadata.create_all rather than a fixed historical schema. To
support both already-deployed V10 and clean installs, add columns only if absent.
"""
from alembic import op
import sqlalchemy as sa

revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None

COLUMNS={
    'users': [('auth_version',sa.Integer(),0)],
    'pages': [('edit_version',sa.Integer(),1),
              ('published_edit_version',sa.Integer(),0),
              ('archived',sa.Boolean(),False)],
    'publications': [('seo_snapshot',sa.JSON(),None)],
}


def upgrade():
    connection=op.get_bind()
    for table, specs in COLUMNS.items():
        existing={c['name'] for c in sa.inspect(connection).get_columns(table)}
        for name, kind, default in specs:
            if name in existing:continue
            if default is None:
                column=sa.Column(name,kind,nullable=True)
            elif isinstance(default,bool):
                column=sa.Column(name,kind,nullable=False,server_default=sa.false())
            else:
                column=sa.Column(name,kind,nullable=False,server_default=str(default))
            op.add_column(table,column)


def downgrade():
    # The initial migration reflects the current metadata; leave the columns in
    # place on downgrade rather than dropping fields now used by model code.
    pass
