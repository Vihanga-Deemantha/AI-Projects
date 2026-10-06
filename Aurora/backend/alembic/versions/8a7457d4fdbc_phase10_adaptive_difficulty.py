"""phase10 adaptive difficulty

Revision ID: 8a7457d4fdbc
Revises: 6bc175274e82
Create Date: 2026-10-05 17:49:30.347658

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a7457d4fdbc'
down_revision: Union[str, Sequence[str], None] = '6bc175274e82'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('conversations', sa.Column('difficulty', sa.Integer(), nullable=True, comment='difficulty tier (1-5) this session ran at; NULL for sessions from before tiers existed'))
    op.add_column('users', sa.Column('difficulty_override', sa.Integer(), nullable=True, comment='difficulty tier (1-5) the learner pinned; NULL = automatic'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'difficulty_override')
    op.drop_column('conversations', 'difficulty')
