"""Build leakage-safe prediction datasets from historical candles."""

from __future__ import annotations

from decimal import Decimal, localcontext

from app.modules.prediction_engine.domain.entities import (
    DirectionLabel,
    PredictionDataset,
    PredictionFeatureRow,
    PredictionHorizon,
    PredictionInputRow,
)
from app.modules.stock_history.domain.entities import (
    HistoricalCandle,
    HistoricalSeries,
)


class PredictionDatasetBuilder:
    """Convert historical OHLCV data into labelled training rows."""

    def build(
        self,
        series: HistoricalSeries,
        *,
        horizon: PredictionHorizon,
        positive_threshold: Decimal,
        negative_threshold: Decimal,
    ) -> PredictionDataset:
        if positive_threshold <= 0:
            raise ValueError("positive_threshold must be positive")

        if negative_threshold >= 0:
            raise ValueError("negative_threshold must be negative")

        rows: list[PredictionFeatureRow] = []
        candles = series.candles
        horizon_sessions = int(horizon)

        # Twenty prior sessions are required for the longest feature.
        first_usable_index = 20
        final_usable_index = len(candles) - horizon_sessions

        for index in range(
            first_usable_index,
            final_usable_index,
        ):
            current = candles[index]
            future = candles[index + horizon_sessions]

            current_close = current.close_price
            future_return = (
                future.close_price / current_close
            ) - Decimal("1")

            rows.append(
                PredictionFeatureRow(
                    display_symbol=series.display_symbol,
                    as_of=current.timestamp,
                    horizon=horizon,
                    close_price=current_close,
                    return_1=self._return_over_sessions(
                        candles,
                        index=index,
                        sessions=1,
                    ),
                    return_5=self._return_over_sessions(
                        candles,
                        index=index,
                        sessions=5,
                    ),
                    return_20=self._return_over_sessions(
                        candles,
                        index=index,
                        sessions=20,
                    ),
                    sma_ratio_5=self._sma_ratio(
                        candles,
                        index=index,
                        sessions=5,
                    ),
                    sma_ratio_20=self._sma_ratio(
                        candles,
                        index=index,
                        sessions=20,
                    ),
                    volatility_5=self._return_volatility(
                        candles,
                        index=index,
                        sessions=5,
                    ),
                    volatility_20=self._return_volatility(
                        candles,
                        index=index,
                        sessions=20,
                    ),
                    volume_ratio_20=self._volume_ratio(
                        candles,
                        index=index,
                        sessions=20,
                    ),
                    candle_body_ratio=self._candle_body_ratio(
                        current
                    ),
                    range_ratio=self._range_ratio(current),
                    future_return=future_return,
                    label=self._label(
                        future_return,
                        positive_threshold=positive_threshold,
                        negative_threshold=negative_threshold,
                    ),
                )
            )

        return PredictionDataset(
            display_symbol=series.display_symbol,
            horizon=horizon,
            rows=tuple(rows),
            positive_threshold=positive_threshold,
            negative_threshold=negative_threshold,
        )

    def build_latest_input(
        self,
        series: HistoricalSeries,
        *,
        horizon: PredictionHorizon,
    ) -> PredictionInputRow:
        """Build an inference row from the newest available candle.

        The latest candle has no known future outcome, so this method
        returns PredictionInputRow rather than fabricating a training
        label or future return.
        """

        candles = series.candles

        if len(candles) < 21:
            raise ValueError(
                "at least 21 candles are required to build "
                "the latest prediction input"
            )

        index = len(candles) - 1
        current = candles[index]

        return PredictionInputRow(
            display_symbol=series.display_symbol,
            as_of=current.timestamp,
            horizon=horizon,
            close_price=current.close_price,
            return_1=self._return_over_sessions(
                candles,
                index=index,
                sessions=1,
            ),
            return_5=self._return_over_sessions(
                candles,
                index=index,
                sessions=5,
            ),
            return_20=self._return_over_sessions(
                candles,
                index=index,
                sessions=20,
            ),
            sma_ratio_5=self._sma_ratio(
                candles,
                index=index,
                sessions=5,
            ),
            sma_ratio_20=self._sma_ratio(
                candles,
                index=index,
                sessions=20,
            ),
            volatility_5=self._return_volatility(
                candles,
                index=index,
                sessions=5,
            ),
            volatility_20=self._return_volatility(
                candles,
                index=index,
                sessions=20,
            ),
            volume_ratio_20=self._volume_ratio(
                candles,
                index=index,
                sessions=20,
            ),
            candle_body_ratio=self._candle_body_ratio(
                current
            ),
            range_ratio=self._range_ratio(current),
        )

    @staticmethod
    def _return_over_sessions(
        candles: tuple[HistoricalCandle, ...],
        *,
        index: int,
        sessions: int,
    ) -> Decimal | None:
        previous_index = index - sessions

        if previous_index < 0:
            return None

        previous_close = candles[previous_index].close_price

        if previous_close == 0:
            return None

        return (
            candles[index].close_price / previous_close
        ) - Decimal("1")

    @staticmethod
    def _sma_ratio(
        candles: tuple[HistoricalCandle, ...],
        *,
        index: int,
        sessions: int,
    ) -> Decimal | None:
        start = index - sessions + 1

        if start < 0:
            return None

        closes = [
            candle.close_price
            for candle in candles[start : index + 1]
        ]

        average = sum(
            closes,
            start=Decimal("0"),
        ) / Decimal(len(closes))

        if average == 0:
            return None

        return candles[index].close_price / average

    def _return_volatility(
        self,
        candles: tuple[HistoricalCandle, ...],
        *,
        index: int,
        sessions: int,
    ) -> Decimal | None:
        start = index - sessions

        if start < 0:
            return None

        returns: list[Decimal] = []

        for candle_index in range(start + 1, index + 1):
            previous_close = candles[
                candle_index - 1
            ].close_price

            if previous_close == 0:
                return None

            returns.append(
                (
                    candles[candle_index].close_price
                    / previous_close
                )
                - Decimal("1")
            )

        if not returns:
            return None

        mean_return = sum(
            returns,
            start=Decimal("0"),
        ) / Decimal(len(returns))

        variance = sum(
            (
                (value - mean_return)
                * (value - mean_return)
                for value in returns
            ),
            start=Decimal("0"),
        ) / Decimal(len(returns))

        with localcontext() as context:
            context.prec = 28
            return variance.sqrt()

    @staticmethod
    def _volume_ratio(
        candles: tuple[HistoricalCandle, ...],
        *,
        index: int,
        sessions: int,
    ) -> Decimal | None:
        start = index - sessions

        if start < 0:
            return None

        # Current volume is compared with previous sessions only.
        previous_volumes = [
            candle.volume
            for candle in candles[start:index]
        ]

        if not previous_volumes:
            return None

        average_volume = (
            Decimal(sum(previous_volumes))
            / Decimal(len(previous_volumes))
        )

        if average_volume == 0:
            return None

        return (
            Decimal(candles[index].volume)
            / average_volume
        )

    @staticmethod
    def _candle_body_ratio(
        candle: HistoricalCandle,
    ) -> Decimal | None:
        candle_range = (
            candle.high_price - candle.low_price
        )

        if candle_range == 0:
            return None

        body = abs(
            candle.close_price - candle.open_price
        )

        return body / candle_range

    @staticmethod
    def _range_ratio(
        candle: HistoricalCandle,
    ) -> Decimal | None:
        if candle.close_price == 0:
            return None

        return (
            candle.high_price - candle.low_price
        ) / candle.close_price

    @staticmethod
    def _label(
        future_return: Decimal,
        *,
        positive_threshold: Decimal,
        negative_threshold: Decimal,
    ) -> DirectionLabel:
        if future_return >= positive_threshold:
            return DirectionLabel.BULLISH

        if future_return <= negative_threshold:
            return DirectionLabel.BEARISH

        return DirectionLabel.NEUTRAL
