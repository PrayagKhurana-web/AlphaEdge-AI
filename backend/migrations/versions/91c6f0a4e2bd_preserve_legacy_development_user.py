"""preserve legacy development user

Revision ID: 91c6f0a4e2bd
Revises: 7b4f1c8d2a91
Create Date: 2026-07-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "91c6f0a4e2bd"
down_revision: Union[str, None] = "7b4f1c8d2a91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


LEGACY_EMAIL = "legacy-development@invalid.local"
LEGACY_PASSWORD_HASH = '$argon2id$v=19$m=65536,t=3,p=4$ElwrEYn/pAnczaQsH/vghw$ezg2q6NBsbKdpoWglt5N1QCoYNZUgdkV+mtZyUS+FCQ'


def upgrade() -> None:
    connection = op.get_bind()

    existing_user = connection.execute(
        sa.text(
            "SELECT id FROM users WHERE id = 1 LIMIT 1"
        )
    ).scalar_one_or_none()

    legacy_watchlist_count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM watchlist_items "
            "WHERE user_id = 1"
        )
    ).scalar_one()

    legacy_portfolio_count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM portfolio_holdings "
            "WHERE user_id = 1"
        )
    ).scalar_one()

    legacy_data_exists = (
        legacy_watchlist_count > 0
        or legacy_portfolio_count > 0
    )

    if existing_user is None and legacy_data_exists:
        connection.execute(
            sa.text(
                """
                INSERT INTO users (
                    id,
                    email,
                    password_hash,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (
                    1,
                    :email,
                    :password_hash,
                    0,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "email": LEGACY_EMAIL,
                "password_hash": LEGACY_PASSWORD_HASH,
            },
        )


def downgrade() -> None:
    connection = op.get_bind()

    legacy_watchlist_count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM watchlist_items "
            "WHERE user_id = 1"
        )
    ).scalar_one()

    legacy_portfolio_count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM portfolio_holdings "
            "WHERE user_id = 1"
        )
    ).scalar_one()

    if (
        legacy_watchlist_count == 0
        and legacy_portfolio_count == 0
    ):
        connection.execute(
            sa.text(
                """
                DELETE FROM users
                WHERE id = 1
                  AND email = :email
                  AND is_active = 0
                """
            ),
            {"email": LEGACY_EMAIL},
        )
