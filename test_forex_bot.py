import csv
import os
import tempfile
import time
from decimal import Decimal

import threading

from forex_bot import (
    ForexBot, IBapi, IDEALPRO_MIN_EURUSD, MAX_POSITION_ORDERS, launch_settings, load_strategy,
)
from strategies.macd import MACD


def test_fills_track_position_and_pnl():
    bot = ForexBot.__new__(ForexBot)  # skip __init__, which connects to IB
    bot.ticker, bot.position, bot.cash = "EUR/USD", 0.0, 0.0
    bot.order_events = {}
    bot.pending = {1: "BUY", 2: "SELL"}
    bot.account_position = None
    bot.account_open = {}

    def status(orderId, price):
        bot.order_status(orderId, "Filled", Decimal(1), Decimal(0), price, 0, 0, price, 1, "", 0)

    with tempfile.TemporaryDirectory() as tmp:
        bot.fileName = os.path.join(tmp, "log.csv")
        status(1, 1.10)
        status(1, 1.10)  # IB repeats "Filled"; it must count once
        assert bot.position == 1
        status(2, 1.12)
        assert bot.position == 0
        assert abs(bot.cash - 0.02) < 1e-9

        with open(bot.fileName) as log:
            rows = list(csv.reader(log))
    assert [r[1] for r in rows] == ["Action", "BUY", "SELL"]
    assert float(rows[2][6]) == 0.02


def test_error_callback_handles_both_ibapi_signatures():
    seen = []
    bot = ForexBot.__new__(ForexBot)
    bot.on_error = lambda reqId, code, msg: seen.append((code, msg))
    api = IBapi(bot)
    api.error(-1, 502, "old style", "")
    api.error(-1, 1700000000000, 502, "new style", "")
    assert seen == [(502, "old style"), (502, "new style")]


def macd_signals(prices, cooldown=0):
    macd = MACD(cooldown=cooldown)
    return [s for p in prices if (s := macd.on_tick(p, p))]


def test_macd_trades_slow_crosses_once_each():
    step = 0.00005
    prices = [1.10 - step * i for i in range(100)]
    prices += [prices[-1] + step * i for i in range(200)]
    prices += [prices[-1] - step * i for i in range(200)]
    assert macd_signals(prices) == ["BUY", "SELL"]
    assert macd_signals(prices, cooldown=3600) == ["BUY"]


def test_macd_does_not_trade_on_the_first_move_after_start_up():
    assert macd_signals([1.10] * 60 + [1.10 + 0.00005 * i for i in range(100)]) == []


class Stub:
    def __init__(self, answers):
        self.answers, self.seen = answers, []

    def on_tick(self, bid, ask):
        self.seen.append((bid, ask))
        return self.answers.pop(0)


def test_bot_turns_strategy_signals_into_orders():
    orders = []
    bot = ForexBot.__new__(ForexBot)
    bot.stopping = threading.Event()
    bot.last_bid = bot.last_ask = None
    bot.quantity = bot.max_position = 3
    bot.position = 0.0
    bot.pending = {}
    bot.account_position = None
    bot.account_open = {}
    bot.symbol = "EUR"
    bot.currency = "USD"
    bot.strategy = Stub(["BUY", "buy", None])
    bot.place_market_order = lambda action, quantity: orders.append((action, quantity))

    bot.tick_price(1, 1, 1.10, None)
    assert bot.strategy.seen == []
    bot.tick_price(1, 2, 1.12, None)
    assert bot.strategy.seen == [(1.10, 1.12)]
    for _ in range(2):
        bot.tick_price(1, 1, 1.10, None)
        bot.tick_price(1, 2, 1.12, None)
    assert orders == [("BUY", 3)]


def test_strategy_orders_stop_at_two_full_positions():
    orders = []
    bot = ForexBot.__new__(ForexBot)
    bot.stopping = threading.Event()
    bot.last_bid = bot.last_ask = None
    bot.quantity = 20000
    bot.max_position = MAX_POSITION_ORDERS * bot.quantity
    bot.position = 0.0
    bot.pending = {}
    bot.account_position = None
    bot.account_open = {}
    bot.symbol = "EUR"
    bot.currency = "USD"
    bot.strategy = Stub(["BUY", "BUY", "BUY"])
    bot.place_market_order = lambda action, quantity: (
        orders.append((action, quantity)), bot.pending.setdefault(len(orders), action)
    )

    for _ in range(3):
        bot.tick_price(1, 1, 1.10, None)
        bot.tick_price(1, 2, 1.12, None)
    assert orders == [("BUY", 20000), ("BUY", 20000)]

    bot.pending.clear()
    bot.position = -40000
    bot.strategy = Stub(["SELL"])
    bot.tick_price(1, 1, 1.10, None)
    bot.tick_price(1, 2, 1.12, None)
    assert orders == [("BUY", 20000), ("BUY", 20000)]


def test_max_position_uses_ib_account_holdings():
    orders = []
    bot = ForexBot.__new__(ForexBot)
    bot.stopping = threading.Event()
    bot.last_bid = bot.last_ask = None
    bot.quantity = 20000
    bot.max_position = 40000
    bot.position = 0.0
    bot.pending = {}
    bot.account_position = 40000
    bot.account_open = {}
    bot.account_as_of = time.time()
    bot.symbol = "EUR"
    bot.currency = "USD"
    bot.strategy = Stub(["BUY"])
    bot.place_market_order = lambda action, quantity: orders.append((action, quantity))
    bot.ensure_account_snapshot = lambda *a, **k: True

    bot.tick_price(1, 1, 1.10, None)
    bot.tick_price(1, 2, 1.12, None)
    assert orders == []

    from ibapi.contract import Contract
    contract = Contract()
    contract.symbol, contract.currency, contract.secType = "EUR", "USD", "CASH"
    other = Contract()
    other.symbol, other.currency, other.secType = "GBP", "USD", "CASH"
    bot._pos_seen = 0.0
    bot.positions_event = threading.Event()
    bot.on_position("DU123", other, 99000, 1.0)
    bot.on_position("DU123", contract, 25000, 1.1)
    bot.on_position_end()
    assert bot.account_position == 25000
    assert bot.positions_event.is_set()


def test_load_strategy_finds_strategies_by_file_name():
    assert isinstance(load_strategy("macd"), MACD)
    try:
        load_strategy("no_such_strategy")
    except ModuleNotFoundError as e:
        assert "no_such_strategy" in str(e)
    else:
        raise AssertionError("an unknown strategy name must fail")


def test_launch_settings_default_to_fillable_idealpro_size():
    assert launch_settings(["forex_bot.py"]) == ("macd", 4002, IDEALPRO_MIN_EURUSD)
    assert launch_settings(["forex_bot.py", "macd", "7497"]) == ("macd", 7497, IDEALPRO_MIN_EURUSD)
    assert launch_settings(["forex_bot.py", "macd", "7497", "25000"]) == ("macd", 7497, 25000.0)
    try:
        launch_settings(["forex_bot.py", "macd", "7497", "0"])
    except ValueError as e:
        assert "positive" in str(e)
    else:
        raise AssertionError("quantity 0 must fail")


if __name__ == "__main__":
    test_fills_track_position_and_pnl()
    test_error_callback_handles_both_ibapi_signatures()
    test_macd_trades_slow_crosses_once_each()
    test_macd_does_not_trade_on_the_first_move_after_start_up()
    test_bot_turns_strategy_signals_into_orders()
    test_strategy_orders_stop_at_two_full_positions()
    test_max_position_uses_ib_account_holdings()
    test_load_strategy_finds_strategies_by_file_name()
    test_launch_settings_default_to_fillable_idealpro_size()
    print("ok")
