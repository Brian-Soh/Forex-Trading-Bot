import time


class Strategy:
    """MACD crossover on the mid price, recalculated on every bid/ask tick."""

    def __init__(self, short=12, long=26, signal=9, cooldown=2.0, diff_eps=1e-5):
        self.ema_short = None
        self.ema_long = None
        self.signal = None
        self.alpha_short = 2 / (short + 1)
        self.alpha_long = 2 / (long + 1)
        self.alpha_signal = 2 / (signal + 1)

        # Crossover control
        self.side = None             # side of the deadband (macd - signal) was last on: "BUY" above, "SELL" below
        self.last_trade_ts = 0.0
        self.cooldown = cooldown     # minimum seconds between trades
        self.diff_eps = diff_eps     # deadband to ignore tiny jitters

    def on_tick(self, bid, ask):
        mid = (bid + ask) / 2.0

        if self.ema_short is None:
            self.ema_short = self.ema_long = mid
            self.signal = 0.0  # the signal line averages the MACD, which starts at 0, not the price
            return None

        # EMA updates
        self.ema_short = (mid - self.ema_short) * self.alpha_short + self.ema_short
        self.ema_long  = (mid - self.ema_long)  * self.alpha_long  + self.ema_long
        macd = self.ema_short - self.ema_long
        self.signal = (macd - self.signal) * self.alpha_signal + self.signal
        diff = macd - self.signal

        print(diff)

        # Trade ONLY on zero-cross with deadband and cooldown.
        # Inside the deadband the side is unchanged, so a cross that takes several ticks still counts.
        side = "BUY" if diff >= self.diff_eps else "SELL" if diff <= -self.diff_eps else self.side
        if side == self.side:
            return None
        if self.side is None:
            self.side = side  # first move after start-up only sets the side, it is not a cross
            return None

        # A cross during the cooldown stays pending and trades once the cooldown ends
        now = time.time()
        if (now - self.last_trade_ts) < self.cooldown:
            return None

        print(f"MACD cross{'↑' if side == 'BUY' else '↓'} → {side} | macd={macd:.6f} signal={self.signal:.6f}")
        self.side = side
        self.last_trade_ts = now
        return side
