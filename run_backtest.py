import argparse
import datetime as dt
import logging
from pathlib import Path
from typing import Any

import backtrader as bt

from dbo_v2_app import SingleTFBreakoutStrategy, load_config
from moex_parser2 import moex_candles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run day_breakout_v2 strategy")
    parser.add_argument(
        "--config",
        default="strategy_config.yaml",
        help="Path to YAML config file",
    )
    parser.add_argument(
        "--mode",
        choices=["backtest", "paper"],
        default=None,
        help="Override mode from config",
    )
    return parser.parse_args()


def setup_logging(level_name: str, log_file: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, mode="a", encoding="utf-8"),
        ],
    )


def _resolve_dates(mode: str, run_cfg: dict[str, Any]) -> tuple[str, str]:
    start = str(run_cfg.get("start", "2025-01-01"))
    end = str(run_cfg.get("end", "2025-03-31"))

    if mode != "paper":
        return start, end

    # Paper mode is a simulation run on the most recent 30 calendar days.
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=30)
    return start_date.isoformat(), end_date.isoformat()


def write_sample_metrics(
    output_path: str,
    *,
    mode: str,
    symbol: str,
    start: str,
    end: str,
    initial_cash: float,
    final_value: float,
) -> None:
    pnl = final_value - initial_cash
    ret_pct = (pnl / initial_cash) * 100 if initial_cash else 0.0

    content = (
        "# Sample Metrics\n\n"
        f"- Mode: `{mode}`\n"
        f"- Symbol: `{symbol}`\n"
        f"- Period: `{start}` -> `{end}`\n"
        f"- Initial cash: `{initial_cash:.2f}`\n"
        f"- Final portfolio value: `{final_value:.2f}`\n"
        f"- Net PnL: `{pnl:.2f}`\n"
        f"- Return: `{ret_pct:.2f}%`\n"
    )

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_strategy(config_path: str, cli_mode: str | None = None) -> float:
    cfg = load_config(config_path)
    run_cfg = cfg.get("run", {})
    strat_cfg = cfg.get("strategy", {})

    mode = cli_mode or str(run_cfg.get("mode", "backtest"))
    symbol = str(run_cfg.get("symbol", "USDRUBF"))
    initial_cash = float(run_cfg.get("initial_cash", 100000))
    log_level = str(run_cfg.get("log_level", "INFO"))
    log_file = str(
        run_cfg.get("log_file", "artifacts/example_logs/trading_robot_strategy.log")
    )
    metrics_output = str(run_cfg.get("metrics_output", "reports/sample_metrics.md"))

    setup_logging(log_level, log_file)
    logger = logging.getLogger("run_backtest")

    tf_min = int(strat_cfg.get("tf_min", 1))
    start, end = _resolve_dates(mode, run_cfg)
    logger.info("Run mode=%s symbol=%s period=%s..%s tf=%s", mode, symbol, start, end, tf_min)

    df_data = moex_candles(symbol, str(tf_min), start, end)

    cerebro = bt.Cerebro()
    datafeed = bt.feeds.PandasData(
        dataname=df_data,
        timeframe=bt.TimeFrame.Minutes,
        compression=tf_min,
    )
    cerebro.adddata(datafeed)

    cerebro.addstrategy(
        SingleTFBreakoutStrategy,
        commission_rate=strat_cfg.get("commission_rate", 0.000166),
        k=strat_cfg.get("k", 0.6),
        stop1_range=strat_cfg.get("stop1_range", 0.5),
        stop2_range=strat_cfg.get("stop2_range", 0.3),
        big_move_threshold=strat_cfg.get("big_move_threshold", 0.025),
        min_range=strat_cfg.get("min_range", 0.01),
        exclude_weekends=strat_cfg.get("exclude_weekends", True),
        wait_hours=strat_cfg.get("wait_hours", 1),
        tf_min=tf_min,
        amount=strat_cfg.get("amount", 0.98),
        test=strat_cfg.get("test", True),
    )

    cerebro.broker.setcash(initial_cash)
    cerebro.run()

    final_value = float(cerebro.broker.getvalue())
    logger.info("Final portfolio value: %.2f", final_value)

    write_sample_metrics(
        metrics_output,
        mode=mode,
        symbol=symbol,
        start=start,
        end=end,
        initial_cash=initial_cash,
        final_value=final_value,
    )
    logger.info("Saved metrics to %s", metrics_output)
    return final_value


def main() -> None:
    args = parse_args()
    run_strategy(config_path=args.config, cli_mode=args.mode)


if __name__ == "__main__":
    main()
