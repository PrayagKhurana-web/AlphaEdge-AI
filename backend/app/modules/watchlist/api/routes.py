"""API routes for the watchlist module."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from app.modules.auth.api.dependencies import (
    VerifiedCurrentUserDependency,
)

from app.modules.watchlist.api.dependencies import (
    WatchlistServiceDependency,
)
from app.modules.watchlist.api.schemas import (
    AddWatchlistItemRequest,
    WatchlistItemResponse,
    WatchlistResponse,
)
from app.modules.watchlist.application.service import (
    InvalidWatchlistSymbolError,
)
from app.modules.watchlist.domain.exceptions import (
    WatchlistItemAlreadyExistsError,
    WatchlistItemNotFoundError,
)


router = APIRouter(
    prefix="/api/v1/watchlist",
    tags=["Watchlist"],
)



def _error_detail(code: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "message": message,
    }


@router.get(
    "",
    response_model=WatchlistResponse,
    summary="Get the current user's watchlist",
)
async def get_watchlist(
    watchlist_service: WatchlistServiceDependency,
    current_user: VerifiedCurrentUserDependency,
) -> WatchlistResponse:
    items = await watchlist_service.list_items(
        user_id=current_user.id,
    )

    return WatchlistResponse.from_domain(items)


@router.post(
    "",
    response_model=WatchlistItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a stock to the current user's watchlist",
)
async def add_watchlist_item(
    payload: AddWatchlistItemRequest,
    watchlist_service: WatchlistServiceDependency,
    current_user: VerifiedCurrentUserDependency,
) -> WatchlistItemResponse:
    try:
        item = await watchlist_service.add_item(
            user_id=current_user.id,
            display_symbol=payload.display_symbol,
        )
    except InvalidWatchlistSymbolError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(
                "INVALID_WATCHLIST_SYMBOL",
                str(exc),
            ),
        ) from exc
    except WatchlistItemAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_error_detail(
                "WATCHLIST_ITEM_ALREADY_EXISTS",
                str(exc),
            ),
        ) from exc

    return WatchlistItemResponse.from_domain(item)


@router.delete(
    "/{display_symbol}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a stock from the current user's watchlist",
)
async def remove_watchlist_item(
    watchlist_service: WatchlistServiceDependency,
    current_user: VerifiedCurrentUserDependency,
    display_symbol: Annotated[
        str,
        Path(
            min_length=5,
            max_length=32,
            description="Stock symbol in SYMBOL.NSE or SYMBOL.BSE format.",
        ),
    ],
) -> None:
    try:
        await watchlist_service.remove_item(
            user_id=current_user.id,
            display_symbol=display_symbol,
        )
    except InvalidWatchlistSymbolError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(
                "INVALID_WATCHLIST_SYMBOL",
                str(exc),
            ),
        ) from exc
    except WatchlistItemNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error_detail(
                "WATCHLIST_ITEM_NOT_FOUND",
                str(exc),
            ),
        ) from exc
