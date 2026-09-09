"""add corrections table

Revision ID: 44201b26c178
Revises: 743b55240af5
Create Date: 2026-09-09 17:43:40.365286

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '44201b26c178'
down_revision: Union[str, Sequence[str], None] = '743b55240af5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('corrections',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('message_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('conversation_id', sa.String(length=36), nullable=False),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('subtype', sa.String(length=50), nullable=False),
    sa.Column('original', sa.Text(), nullable=False),
    sa.Column('correction', sa.Text(), nullable=False),
    sa.Column('explanation', sa.Text(), nullable=False),
    sa.Column('is_error', sa.Boolean(), nullable=False),
    sa.Column('severity', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('corrections')
