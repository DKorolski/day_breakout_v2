# day_breakout_v2

What it is: Intraday breakout strategy (Backtrader/Python) with YAML config + reproducible runs.

Quickstart: `pip install -r requirements.txt && python3 run_backtest.py --config strategy_config.yaml`

Config: see `strategy_config.yaml` (table below).

Limitations: backtest assumptions, fees/slippage, market schedule.

## Strategy Rules (10 lines)

1. Build yesterday's high/low/close and daily range from intraday candles.
2. Skip trading on weekends when `exclude_weekends=true`.
3. Wait `wait_hours` from session start before allowing new entries.
4. Do not trade when yesterday's range is below `min_range`.
5. Disable long entries after an overly negative previous day return.
6. Disable short entries after an overly positive previous day return.
7. Long breakout level is `yesterday_close + k * yesterday_range`.
8. Short breakout level is `yesterday_close - k * yesterday_range`.
9. Position size is fixed to 1 in test mode, otherwise based on cash and `amount`.
10. Exit with stop logic (`stop1_range`, `stop2_range`) and end-of-day close rule.

## Market / Timeframe

- Market: MOEX futures stream via `aiomoex` (default symbol: `USDRUBF`).
- Base timeframe: 1-minute candles (`tf_min` in config).
- Engine: Backtrader.
- Data source: `moex_parser2.py`.

## Config

### `run` section

| Name | Meaning | Typical range / values |
|---|---|---|
| `symbol` | Instrument ticker | `USDRUBF` (or other MOEX symbol) |
| `start` | Backtest start date | `YYYY-MM-DD` |
| `end` | Backtest end date | `YYYY-MM-DD` |
| `mode` | Run mode | `backtest` or `paper` |
| `initial_cash` | Starting cash | `> 0` |
| `log_level` | Logging verbosity | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `log_file` | Log output path | e.g. `artifacts/example_logs/trading_robot_strategy.log` |
| `metrics_output` | Metrics markdown output | e.g. `reports/sample_metrics.md` |

### `strategy` section

| Name | Meaning | Typical range / values |
|---|---|---|
| `commission_rate` | Commission per trade | `0.00005`-`0.001` |
| `k` | Breakout multiplier for yesterday range | `0.2`-`1.5` |
| `stop1_range` | Intraday stop level #1 (fraction of yesterday range) | `0.1`-`1.0` |
| `stop2_range` | Intraday stop level #2 (fraction of yesterday range) | `0.05`-`0.8` |
| `big_move_threshold` | Filter for strong previous-day return | `0.005`-`0.05` |
| `min_range` | Minimal yesterday range required to trade | `0.001`-`0.05` |
| `exclude_weekends` | Skip weekends | `true` / `false` |
| `wait_hours` | No-entry buffer from session start | `0`-`3` |
| `tf_min` | Candle compression in minutes | `1`, `5`, `10`, ... |
| `amount` | Fraction of available cash to allocate | `0.1`-`1.0` |
| `test` | Fixed lot mode | `true` / `false` |

## How to Run

### Backtest

```bash
python3 run_backtest.py --config strategy_config.yaml --mode backtest
```

### Paper (simulation mode)

```bash
python3 run_backtest.py --config strategy_config.yaml --mode paper
```

Note: `paper` here is a simulation run over the most recent 30 calendar days (no real broker routing).

## Market Schedule Notes

- Weekend bars are skipped when `exclude_weekends=true`.
- The strategy waits `wait_hours` after session start to avoid open-noise entries.
- End-of-day close logic currently triggers at `23:40` strategy time.
- MOEX clearing breaks/holiday microstructure are not fully modeled in this showcase.

## Reproducible Run

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run with explicit config:

```bash
python3 run_backtest.py --config strategy_config.yaml
```

3. Check artifacts:

- Logs: `artifacts/example_logs/trading_robot_strategy.log`
- Metrics: `reports/sample_metrics.md`
- Equity sample image: `reports/sample_equity.png`

## Results Artifacts

- [Sample metrics](reports/sample_metrics.md)
- [Sample equity curve image](reports/sample_equity.png)
