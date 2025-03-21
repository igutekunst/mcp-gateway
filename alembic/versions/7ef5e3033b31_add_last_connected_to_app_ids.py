"""add last_connected to app_ids

Revision ID: 7ef5e3033b31
Revises: cc782dc241c1
Create Date: 2024-03-21 12:34:56.789012

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7ef5e3033b31'
down_revision: Union[str, None] = 'cc782dc241c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add last_connected column to app_ids table
    op.add_column('app_ids', sa.Column('last_connected', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove last_connected column from app_ids table
    op.drop_column('app_ids', 'last_connected')
