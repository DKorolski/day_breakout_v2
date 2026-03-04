import pandas as pd

from moex_parser2 import candles_resample


def test_candles_resample_aggregates_ohlcv() -> None:
    idx = pd.to_datetime(
        [
            "2025-01-01 10:00:00",
            "2025-01-01 10:01:00",
            "2025-01-01 10:02:00",
            "2025-01-01 10:03:00",
        ]
    )
    df = pd.DataFrame(
        {
            "Open": [100.0, 102.0, 103.0, 101.0],
            "Close": [102.0, 103.0, 101.0, 105.0],
            "High": [103.0, 104.0, 104.0, 106.0],
            "Low": [99.0, 101.0, 100.0, 100.0],
            "Volume": [10, 15, 20, 25],
        },
        index=idx,
    )
    df.index.name = "Date"

    result = candles_resample(df, "2min")

    assert len(result) == 2
    assert result.iloc[0]["Open"] == 100.0
    assert result.iloc[0]["Close"] == 103.0
    assert result.iloc[0]["High"] == 104.0
    assert result.iloc[0]["Low"] == 99.0
    assert result.iloc[0]["Volume"] == 25


def test_candles_resample_supports_date_column() -> None:
    df = pd.DataFrame(
        {
            "Date": ["2025-01-01 10:00:00", "2025-01-01 10:01:00"],
            "Open": [100.0, 101.0],
            "Close": [101.0, 102.0],
            "High": [102.0, 103.0],
            "Low": [99.0, 100.0],
            "Volume": [10, 15],
        }
    )

    result = candles_resample(df, "2min")

    assert len(result) == 1
    assert result.iloc[0]["Open"] == 100.0
    assert result.iloc[0]["Close"] == 102.0
    assert result.iloc[0]["Volume"] == 25
