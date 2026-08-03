"""API schemas for the watchlist module."""

from __future__ import annotations

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.modules.watchlist.domain.entities import WatchlistItem


class AddWatchlistItemRequest(BaseModel):
    """Payload for adding one stock to the watchlist."""

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    display_symbol: str = Field(
        alias="displaySymbol",
        min_length=5,
        max_length=32,
        examples=["RELIANCE.NSE"],
    )


class WatchlistItemResponse(BaseModel):
    """One stock saved in the user's watchlist."""

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    id: int
    display_symbol: str = Field(alias="displaySymbol")
    exchange: str
    created_at: AwareDatetime = Field(alias="createdAt")

    @classmethod
    def from_domain(
        cls,
        item: WatchlistItem,
    ) -> "WatchlistItemResponse":
        return cls(
            id=item.id,
            displaySymbol=item.display_symbol,
            exchange=item.exchange,
            createdAt=item.created_at,
        )


class WatchlistResponse(BaseModel):
    """Complete watchlist returned by the API."""

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

    items: list[WatchlistItemResponse]
    count: int

    @classmethod
    def from_domain(
        cls,
        items: list[WatchlistItem],
    ) -> "WatchlistResponse":
        return cls(
            items=[
                WatchlistItemResponse.from_domain(item)
                for item in items
            ],
            count=len(items),
        )
