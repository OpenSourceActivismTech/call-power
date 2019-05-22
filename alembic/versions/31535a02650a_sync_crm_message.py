"""sync crm message

Revision ID: 31535a02650a
Revises: 07a850f06c80
Create Date: 2019-05-22 13:40:08.397086

"""

# revision identifiers, used by Alembic.
revision = '31535a02650a'
down_revision = '07a850f06c80'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('sync_call', schema=None) as batch_op:
        batch_op.add_column(sa.Column('crm_message', sa.String(), nullable=True))
  # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('sync_call', schema=None) as batch_op:
        batch_op.drop_column('crm_message')
    # ### end Alembic commands ###
