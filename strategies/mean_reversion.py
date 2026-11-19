import time
from collections import deque


class MeanReversion:
    """Fade moves that stretch too far from a short rolling mid-price average.

    Opposite style to MACD: buy after a sharp drop (z below -entry), sell after a
    sharp rise (z above +entry). Needs `window` quotes before it can trade.
    """

    def __init__(self, window=50, entry_z=2.0, cooldown=2.0):
        self.mids = deque(maxlen=window)
        self.entry_z = entry_z
        self.cooldown = cooldown
        self.in_zone = None          # extreme we are already in: "BUY", "SELL", or None
        self.last_trade_ts = 0.0

    def on_tick(self, bid, ask):
        mid = (bid + ask) / 2.0
        self.mids.append(mid)
        if len(self.mids) < self.mids.maxlen:
            return None

        mean = sum(self.mids) / len(self.mids)
        var = sum((x - mean) ** 2 for x in self.mids) / len(self.mids)
        std = var ** 0.5
        if std < 1e-12:
            return None

        z = (mid - mean) / std
        print(z)

        zone = "BUY" if z <= -self.entry_z else "SELL" if z >= self.entry_z else None
        if zone is None:
            self.in_zone = None
            return None
        if zone == self.in_zone:
            return None

        now = time.time()
        if (now - self.last_trade_ts) < self.cooldown:
            return None

        print(f"Mean reversion z={z:.3f} → {zone}")
        self.in_zone = zone
        self.last_trade_ts = now
        return zone


Strategy = MeanReversion
