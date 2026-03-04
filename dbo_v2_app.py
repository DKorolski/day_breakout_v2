import datetime
import logging
from pathlib import Path

import backtrader as bt
import yaml

from moex_parser2 import moex_candles

logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)


def load_config(config_path: str = "strategy_config.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if not isinstance(config, dict):
        raise ValueError(f"Config must be a dictionary, got: {type(config).__name__}")
    return config

class SingleTFBreakoutStrategy(bt.Strategy):
    params = (
        ('commission_rate', 0.00017),  # комиссия
        ('k', 0.6),                    # коэффициент для прорыва
        ('stop1_range', 0.5),          # стоп 1: 50% диапазона предыдущего дня
        ('stop2_range', 0.3),          # стоп 2: 30% диапазона предыдущего дня
        ('big_move_threshold', 0.025), # ±2.5% для фильтра движения
        ('min_range', 0.01),           # минимум диапазона в 1%
        ('exclude_weekends', True),
        ('wait_hours', 1),             # ожидание в часах после открытия дня
        ('tf_min', 1),                 # основной таймфрейм – 10 минут
        ('amount', 0.98),
        ('test', False)                # новый параметр: если True, то лот = 1
    )
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # "Текущий день":
        self.cur_day_date = None
        self.cur_day_open = None
        self.cur_day_high = None
        self.cur_day_low  = None
        self.cur_day_close = None
        
        # "Вчерашний" день:
        self.yesterday_close = None
        self.yesterday_high  = None
        self.yesterday_low   = None
        self.yesterday_range = None
        self.yesterday_return = None

        # День "позапрошлый"
        self.day_before_close = None
        
        # Флаги входа за день
        self.was_long_today = False
        self.was_short_today = False
        
        # Время начала торговой сессии текущего дня
        self.today_start = None
        
        self.order = None
    
    def start(self):
        self.broker.setcommission(commission=self.p.commission_rate)
    
    def next(self):
        dt0 = self.data.datetime.datetime(0)
        close0 = self.data.close[0]
        high0  = self.data.high[0]
        low0   = self.data.low[0]
        open0  = self.data.open[0]
        
        # Пример: если время 23:00 и открыта позиция, то закрываем позицию.
        if dt0.hour == 23 and dt0.minute == 40 and self.position:
            self.logger.info(f"End of day exit triggered at {dt0} – closing position.")
            self.close()
        
        # (1) Пропускаем выходные
        if self.p.exclude_weekends and dt0.weekday() in [5, 6]:
            self.logger.debug(f"{dt0} – weekend, skip trading.")
            return
        
        # (2) Проверяем переход на новый день
        if self.cur_day_date is None:
            self._init_new_day(dt0, open0)
        else:
            if dt0.date() != self.cur_day_date:
                self._on_day_close()
                self._init_new_day(dt0, open0)

        # Обновляем показатели текущего дня
        self._update_cur_day(high0, low0, close0)
        
        # (3) Инициализируем время начала, если ещё не установлено
        if self.today_start is None:
            self.today_start = dt0
        
        # (4) Если позиция открыта – проверяем стопы
        if self.position:
            self._check_stops(dt0, close0)
        
        # (5) Если позиции нет – проверяем возможность входа
        if not self.position:
            delta_h = (dt0 - self.today_start).total_seconds() / 3600.0
            if delta_h >= self.p.wait_hours:
                self._check_entry(dt0, close0)
            else:
                self.logger.debug(f"{dt0} – wait_hours not reached: {delta_h:.2f}h < {self.p.wait_hours}h, skipping entry.")
    
    def _init_new_day(self, dt, open_price):
        self.cur_day_date = dt.date()
        self.cur_day_open = open_price
        self.cur_day_high = open_price
        self.cur_day_low  = open_price
        self.cur_day_close = open_price
        
        self.today_start = datetime.datetime(dt.year, dt.month, dt.day, 0, 0, 0)
        self.logger.info(f"_init_new_day: day={self.cur_day_date}, open={open_price}")
        
        self.was_long_today = False
        self.was_short_today = False

    def _update_cur_day(self, high0, low0, close0):
        if high0 > self.cur_day_high:
            self.cur_day_high = high0
        if low0 < self.cur_day_low:
            self.cur_day_low = low0
        self.cur_day_close = close0

    def _on_day_close(self):
        self.logger.debug(f"_on_day_close: day={self.cur_day_date}, close={self.cur_day_close}, high={self.cur_day_high}, low={self.cur_day_low}")
        self.yesterday_close = self.cur_day_close
        self.yesterday_high  = self.cur_day_high
        self.yesterday_low   = self.cur_day_low
        self.yesterday_range = self.yesterday_high - self.yesterday_low

        if self.day_before_close is not None and self.day_before_close != 0:
            self.yesterday_return = (self.yesterday_close - self.day_before_close) / self.day_before_close
        else:
            self.yesterday_return = None
        
        self.logger.debug(f"Yesterday: close={self.yesterday_close}, range={self.yesterday_range}, return={self.yesterday_return}")
        self.day_before_close = self.cur_day_close
    
    def _check_stops(self, dt, close0):
        if self.position.size > 0:  # длинная позиция
            if self.yesterday_close is not None and self.yesterday_range is not None:
                stop2_level = self.yesterday_close - self.p.stop2_range * self.yesterday_range
                if close0 < stop2_level:
                    self.logger.debug(f"{dt} – LONG STOP2 triggered: close={close0:.2f} < stop2={stop2_level:.2f}. Closing position.")
                    self.close()
        elif self.position.size < 0:  # короткая позиция
            if self.yesterday_close is not None and self.yesterday_range is not None:
                stop2_level = self.yesterday_close + self.p.stop2_range * self.yesterday_range
                if close0 > stop2_level:
                    self.logger.debug(f"{dt} – SHORT STOP2 triggered: close={close0:.2f} > stop2={stop2_level:.2f}. Closing position.")
                    self.close()

        if dt.minute == 50:
            if self.position.size > 0:
                if self.yesterday_close is not None and self.yesterday_range is not None:
                    stop1_level = self.yesterday_close + self.p.stop1_range * self.yesterday_range
                    if close0 < stop1_level:
                        self.logger.debug(f"{dt} – LONG STOP1: close={close0:.2f} < stop1={stop1_level:.2f}. Closing position.")
                        self.close()
            elif self.position.size < 0:
                if self.yesterday_close is not None and self.yesterday_range is not None:
                    stop1_level = self.yesterday_close - self.p.stop1_range * self.yesterday_range
                    if close0 > stop1_level:
                        self.logger.debug(f"{dt} – SHORT STOP1: close={close0:.2f} > stop1={stop1_level:.2f}. Closing position.")
                        self.close()

    def _check_entry(self, dt, close0):
        if self.yesterday_close is None or self.yesterday_range is None:
            self.logger.debug(f"{dt} – no 'yesterday' data: close={self.yesterday_close}, range={self.yesterday_range}. Skipping entry.")
            return
        
        if self.yesterday_range < self.p.min_range:
            self.logger.debug(f"{dt} – yesterday_range={self.yesterday_range:.4f} < min_range={self.p.min_range}. Skipping entry.")
            return
        
        can_long = True
        can_short = True
        if self.yesterday_return is not None:
            if self.yesterday_return < -self.p.big_move_threshold:
                can_long = False
                self.logger.debug(f"{dt} – strong negative move yesterday (ret={self.yesterday_return:.4f}) – no LONG entry.")
            if self.yesterday_return > self.p.big_move_threshold:
                can_short = False
                self.logger.debug(f"{dt} – strong positive move yesterday (ret={self.yesterday_return:.4f}) – no SHORT entry.")
        
        long_level  = self.yesterday_close + self.p.k * self.yesterday_range
        short_level = self.yesterday_close - self.p.k * self.yesterday_range

        cash = self.broker.getcash()
        # Если тестовый режим, то размер позиции равен 1, иначе рассчитывается по коэффициенту от средств
        if self.p.test:
            lot_size = 1
        else:
            lot_size = int((cash * self.p.amount) / close0) if close0 else 0

        if lot_size <= 0:
            self.logger.debug(f"{dt} – insufficient cash for entry: cash={cash:.2f}, close={close0:.2f}")
            return

        if can_long and not self.was_long_today:
            if close0 > long_level:
                self.logger.info(f"{dt} – ENTER LONG: close={close0:.2f} > long_level={long_level:.2f} with lot_size={lot_size}")
                self.buy(size=lot_size)
                self.was_long_today = True
        if can_short and not self.was_short_today:
            if close0 < short_level:
                self.logger.info(f"{dt} – ENTER SHORT: close={close0:.2f} < short_level={short_level:.2f} with lot_size={lot_size}")
                self.sell(size=lot_size)
                self.was_short_today = True
    
    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                self.logger.info(f"{order.data.datetime.datetime(0)} – BUY filled: price={order.executed.price:.2f}, size={order.executed.size}")
            else:
                self.logger.info(f"{order.data.datetime.datetime(0)} – SELL filled: price={order.executed.price:.2f}, size={order.executed.size}")
            self.order = None
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.logger.warning(f"[ORDER] Canceled/Margin/Rejected: status={order.status}")
            self.order = None
    
    def notify_trade(self, trade):
        if trade.isclosed:
            self.logger.info(f"[TRADE] closed: PnL={trade.pnl:.2f}, Net={trade.pnlcomm:.2f}")

def main() -> None:
    log_path = Path("artifacts/example_logs/trading_robot_strategy.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                str(log_path), mode="a", encoding="utf-8"
            ),
        ],
    )
    logger = logging.getLogger("Main")
    logger.info("Старт стратегии")

    config_path = Path("strategy_config.yaml")
    config = load_config(str(config_path))
    strat_params = config.get("strategy", {})
    logger.debug(f"Загруженные параметры стратегии: {strat_params}")
    tf_min = int(strat_params.get("tf_min", 1))
    df_data = moex_candles("USDRUBF", str(tf_min), "2025-01-01", "2025-03-31")

    cerebro = bt.Cerebro()
    datafeed = bt.feeds.PandasData(
        dataname=df_data,
        timeframe=bt.TimeFrame.Minutes,
        compression=tf_min,
    )
    cerebro.adddata(datafeed)

    cerebro.addstrategy(
        SingleTFBreakoutStrategy,
        commission_rate=strat_params.get("commission_rate", 0.000066),
        k=strat_params.get("k", 0.6),
        stop1_range=strat_params.get("stop1_range", 0.5),
        stop2_range=strat_params.get("stop2_range", 0.3),
        big_move_threshold=strat_params.get("big_move_threshold", 0.025),
        min_range=strat_params.get("min_range", 0.01),
        exclude_weekends=strat_params.get("exclude_weekends", True),
        wait_hours=strat_params.get("wait_hours", 0),
        tf_min=tf_min,
        amount=strat_params.get("amount", 0.98),
        test=strat_params.get("test", False),
    )
    cerebro.broker.setcash(100000.0)
    cerebro.addanalyzer(bt.analyzers.PyFolio, _name="PyFolio")

    cerebro.run()
    logger.info(f"Final Portfolio Value: {cerebro.broker.getvalue():.2f}")


if __name__ == "__main__":
    main()
