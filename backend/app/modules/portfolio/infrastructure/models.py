from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base


class PortfolioHoldingModel(Base):
    """Persisted portfolio holding."""

    __tablename__ = "portfolio_holdings"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "display_symbol",
            name="uq_portfolio_user_symbol",
        ),
        CheckConstraint(
            "quantity > 0",
            name="ck_portfolio_quantity_positive",
        ),
        CheckConstraint(
            "average_buy_price > 0",
            name="ck_portfolio_average_price_positive",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    display_symbol: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    exchange: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(20, 6),
        nullable=False,
    )
    average_buy_price: Mapped[Decimal] = mapped_column(
        Numeric(20, 4),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
