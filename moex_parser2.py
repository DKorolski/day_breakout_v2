import asyncio
from typing import Any

import pandas as pd


def _run(coro: Any) -> Any:
    try:
        return asyncio.run(coro)
    except RuntimeError as exc:
        if "asyncio.run() cannot be called" in str(exc):
            raise RuntimeError(
                "Cannot run fetch function inside an active event loop."
            ) from exc
        raise


def _normalize_candles(data: list[dict[str, Any]]) -> pd.DataFrame:
    if not data:
        return pd.DataFrame(
            columns=["Open", "Close", "High", "Low", "Volume", "Adj Close"]
        )

    df = pd.DataFrame(data)
    df = df.rename(
        columns={
            "open": "Open",
            "close": "Close",
            "high": "High",
            "low": "Low",
            "volume": "Volume",
        }
    )

    required = {"begin", "Open", "Close", "High", "Low", "Volume"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"MOEX response is missing expected fields: {sorted(missing)}")

    df["Date"] = pd.to_datetime(df["begin"])
    df = df.set_index("Date")[["Open", "Close", "High", "Low", "Volume"]]
    df["Adj Close"] = df["Close"]
    return df


async def _fetch_board_candles(
    security: str,
    interval: str,
    start: str,
    end: str,
    *,
    board: str = "TQBR",
    engine: str | None = None,
    market: str | None = None,
) -> pd.DataFrame:
    import aiohttp
    import aiomoex

    request_args: dict[str, Any] = {
        "session": None,
        "security": security,
        "interval": interval,
        "start": start,
        "end": end,
        "board": board,
    }
    if engine:
        request_args["engine"] = engine
    if market:
        request_args["market"] = market

    async with aiohttp.ClientSession() as session:
        request_args["session"] = session
        data = await aiomoex.get_board_candles(**request_args)
    return _normalize_candles(data)


def moex_candles(security: str, interval: str, start: str, end: str) -> pd.DataFrame:
    return _run(
        _fetch_board_candles(
            security=security,
            interval=interval,
            start=start,
            end=end,
            engine="futures",
            market="forts",
            board="TQBR",
        )
    )


def moex_candles_stock(
    security: str, interval: str, start: str, end: str
) -> pd.DataFrame:
    return _run(
        _fetch_board_candles(
            security=security,
            interval=interval,
            start=start,
            end=end,
            board="TQBR",
        )
    )


def candles_resample(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    if "Date" in df.columns:
        local_df = df.copy()
        local_df["Date"] = pd.to_datetime(local_df["Date"])
        local_df = local_df.set_index("Date")
    else:
        local_df = df.copy()
        local_df.index = pd.to_datetime(local_df.index)
        local_df.index.name = "Date"

    agg_map = {
        "Open": "first",
        "Close": "last",
        "High": "max",
        "Low": "min",
        "Volume": "sum",
    }
    df_resampled = local_df.resample(interval).agg(agg_map)
    df_resampled.dropna(how="all", inplace=True)
    return df_resampled


def moex_candles_index(
    security: str, interval: str, start: str, end: str
) -> pd.DataFrame:
    return _run(
        _fetch_board_candles(
            security=security,
            interval=interval,
            start=start,
            end=end,
            engine="stock",
            market="index",
            board="TQBR",
        )
    )


def moex_candles_option(
    security: str, interval: str, start: str, end: str
) -> pd.DataFrame:
    return _run(
        _fetch_board_candles(
            security=security,
            interval=interval,
            start=start,
            end=end,
            engine="futures",
            market="options",
            board="TQBR",
        )
    )
