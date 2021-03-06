"""campaign_name_length

Revision ID: 07a850f06c80
Revises: cdd4c25989d6
Create Date: 2019-05-17 13:32:35.351585

"""

# revision identifiers, used by Alembic.
revision = '07a850f06c80'
down_revision = 'cdd4c25989d6'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('campaign_campaign', schema=None) as batch_op:
        batch_op.alter_column('name',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.String(length=255),
               existing_nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('campaign_campaign', schema=None) as batch_op:
        batch_op.alter_column('name',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=100),
               existing_nullable=False)
    # ### end Alembic commands ###
