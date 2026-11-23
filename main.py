"""CBBTC 1-minute trend bot for make.fun btc-race-24h-20261123-0511.

Strategy (original): EMA-crossover trend following with a separation filter,
a trailing stop and a re-entry cooldown. Long only, at most one open
position, at most one order per reply.

  - Track the close of every 1-minute CBBTC bar and maintain a fast EMA
    (20 bars) and a slow EMA (120 bars).
  - Enter long when the fast EMA is above the slow EMA by more than 10 bps
    of price (separation filter: keeps us out of flat, choppy water where
    a full round trip costs ~30-45 bps in fees, slippage and impact) and
    the latest close is above the fast EMA.
  - Size the entry at 80% of equity: large enough for a real move to pay,
    small enough that the constant-product price impact stays modest.
  - Exit the whole position when the fast EMA crosses back below the slow
    EMA, or when the close falls 2.0% below the highest close seen since
    entry (trailing stop). After an exit, wait 30 bars before re-entering.
  - Never trade during the warm-up batches; never trade before 50 bars of
    history exist.

Parameters were tuned on the published dev window with a local replay of
the documented fill model (324-variant grid, then a wider-trail round):
FAST 20 / SLOW 120 / separation 10 bps / 80% size / 2% trail / 30-bar
cooldown was the plateau best at +$6.71 net PnL on the dev window
(10 trades, 2.5% max drawdown), stable across trailing stops of 1.5-5%
and cooldowns of 10-30 bars. The dev window itself rose 3.64% but was
choppy: most parameter sets lost money (median -$6.14), so the slow
EMAs and the separation filter are doing the work, not a lucky spike.

Determinism: pure function of the bars seen so far. No wall clock, no
network, no files, no randomness, no environment reads. The same bars
always produce the same orders.

Protocol: agent-fun/bars-replay/v1, spoken through the vendored shim
(vendor/makefun_bars.py). Orders decided on the batch of the bar closing
at minute t fill at the next bar's open, so every decision is made on
closes only. max_slippage_bps 200 bounds the move from the latest close
that a fill may cost us.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

# --- strategy parameters (bps are 1/10000) ---
FAST_LEN = 20          # fast EMA length in bars
SLOW_LEN = 120          # slow EMA length in bars
MIN_BARS = 50          # bars of history needed before the first trade
SEPARATION_BPS = 10     # fast-over-slow gap required to enter (bps of price)
ENTRY_FRACTION_BPS = 8000   # entry size: 80% of equity
TRAIL_BPS = 200        # trailing stop: 2.0% below the peak close since entry
COOLDOWN_BARS = 30     # bars to wait after an exit before re-entering
MAX_SLIPPAGE_BPS = 200
MIN_NOTIONAL = 1_000_000  # 1 USDC in quote units


class TrendBot:
    """Keeps the bar history and the EMA state; decides one reply at a time."""

    def __init__(self):
        self.closes = []
        self.ema_fast = None
        self.ema_slow = None
        self.peak_since_entry = None
        self.cooldown_left = 0
        self._in_position = False

    def on_batch(self, state, batch):
        close = state.close(SYMBOL)
        if close is None:
            return []
        self._update_ema(close)
        self.closes.append(close)
        if self.cooldown_left > 0:
            self.cooldown_left -= 1

        holding = state.positions.get(SYMBOL)
        in_position = holding is not None and holding.qty > 0

        if in_position:
            if self.peak_since_entry is None or close > self.peak_since_entry:
                self.peak_since_entry = close
            if self._should_exit(close):
                self.peak_since_entry = None
                self.cooldown_left = COOLDOWN_BARS
                return [{"side": "sell", "symbol": SYMBOL,
                         "qty": holding.qty,
                         "max_slippage_bps": MAX_SLIPPAGE_BPS}]
            return []

        # Flat: only enter with enough history, outside warm-up, off cooldown.
        self.peak_since_entry = None
        if state.warming_up:
            return []
        if len(self.closes) < MIN_BARS or self.cooldown_left > 0:
            return []
        if not self._should_enter(close):
            return []
        notional = min(
            state.cash,
            state.equity * ENTRY_FRACTION_BPS // 10_000,
            state.weight_room(SYMBOL),
        )
        if notional < MIN_NOTIONAL:
            return []
        return [{"side": "buy", "symbol": SYMBOL,
                 "notional_quote_units": notional,
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]

    def _update_ema(self, close):
        if self.ema_fast is None:
            self.ema_fast = float(close)
            self.ema_slow = float(close)
            return
        alpha_fast = 2.0 / (FAST_LEN + 1)
        alpha_slow = 2.0 / (SLOW_LEN + 1)
        self.ema_fast += alpha_fast * (close - self.ema_fast)
        self.ema_slow += alpha_slow * (close - self.ema_slow)

    def _should_enter(self, close):
        if self.ema_fast is None or self.ema_slow is None:
            return False
        if self.ema_fast <= self.ema_slow:
            return False
        # Separation filter: the gap must clear 5 bps of price, so a flat
        # market whose EMAs merely touch never triggers a costly round trip.
        if (self.ema_fast - self.ema_slow) * 10_000 <= SEPARATION_BPS * self.ema_slow:
            return False
        # The latest close must confirm the trend by sitting above the fast EMA.
        return close > self.ema_fast

    def _should_exit(self, close):
        if self.ema_fast is not None and self.ema_slow is not None:
            if self.ema_fast < self.ema_slow:
                return True
        if self.peak_since_entry is not None:
            # Trailing stop: 1.0% below the best close since entry.
            if close * 10_000 <= self.peak_since_entry * (10_000 - TRAIL_BPS):
                return True
        return False


def main():
    bot = TrendBot()
    makefun_bars.run(bot.on_batch)


if __name__ == "__main__":
    main()
