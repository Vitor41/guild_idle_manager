"""add mission display order

Revision ID: ef8f80ce71ab
Revises: 0287a3a072cd
Create Date: 2026-06-19 16:27:01.764774
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ef8f80ce71ab'
down_revision: Union[str, Sequence[str], None] = '0287a3a072cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'mission_templates',
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
    )
    op.execute('UPDATE mission_templates SET display_order = id')
    op.alter_column('mission_templates', 'display_order', server_default=None)
    op.create_index(op.f('ix_mission_templates_display_order'), 'mission_templates', ['display_order'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_mission_templates_display_order'), table_name='mission_templates')
    op.drop_column('mission_templates', 'display_order')
