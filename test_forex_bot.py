import csv
import os
import tempfile
from decimal import Decimal

from forex_bot import ForexBot, IBapi


def test_fills_track_position_and_pnl():
    bot = ForexBot.__new__(ForexBot)  # skip __init__, which connects to IB
    bot.ticker, bot.position, bot.cash = "EUR/USD", 0.0, 0.0
    bot.order_events = {}
    bot.pending = {1: "BUY", 2: "SELL"}

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


if __name__ == "__main__":
    test_fills_track_position_and_pnl()
    test_error_callback_handles_both_ibapi_signatures()
    print("ok")
