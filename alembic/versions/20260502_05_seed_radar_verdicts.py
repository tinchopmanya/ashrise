"""Seed Radar portfolio verdicts.

Revision ID: 20260502_05
Revises: 20260502_04
Create Date: 2026-05-02
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260502_05"
down_revision: str | None = "20260502_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO radar_config (key, value, description)
        VALUES (
            'verdict',
            '["KILL", "PARK", "ITERATE", "ADVANCE", "ABSORB"]'::jsonb,
            'Radar portfolio review verdicts.'
        )
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value,
            description = EXCLUDED.description
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM radar_config WHERE key = 'verdict'")
