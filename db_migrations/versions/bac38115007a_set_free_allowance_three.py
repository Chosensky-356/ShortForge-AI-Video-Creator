"""set_free_allowance_three

Revision ID: bac38115007a
Revises: 45cb23687c79
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'bac38115007a'
down_revision: Union[str, Sequence[str], None] = '45cb23687c79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE creator_profiles SET monthly_video_allowance = 3 WHERE plan = 'free' AND monthly_video_allowance IN (0, 30);")


def downgrade() -> None:
    pass
