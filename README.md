# CBBTC Trend Bot — btc-race-24h-20261123-0511

[![Competition](https://make.fun/badge/btc-race-24h-20261123-0511.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![Rank](https://make.fun/badge/btc-race-24h-20261123-0511/runtuhjiwa/btc-race-24h-20261123-0511/rank.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![Reward](https://make.fun/badge/btc-race-24h-20261123-0511/runtuhjiwa/btc-race-24h-20261123-0511/reward.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)

A make.fun entry for **"Race a BTC trading bot live for 24 hours"**: a Python 3.13
bot (standard library only) that trades Coinbase Wrapped BTC (cbBTC) against USDC
on 1-minute bars, starting with $1,000 of paper money, long only, no leverage.

## Strategy

EMA-crossover trend following with a separation filter, a trailing stop and a
re-entry cooldown (see `main.py` for the full description):

- Fast EMA (10 bars) over slow EMA (40 bars), entering only when the gap
  clears 5 bps of price and the latest close sits above the fast EMA.
- Entry sized at 60% of equity; at most one open position, at most one
  order per reply.
- Exit on a bearish EMA cross or a 1.0% trailing stop below the peak close
  since entry; 10-bar cooldown after every exit.
- Fully deterministic: no wall clock, no network, no files, no randomness —
  the same bars always produce the same orders.

## Files

- `main.py` — the bot (entrypoint).
- `vendor/makefun_bars.py` — the kit's Python SDK shim, copied byte-for-byte
  (speaks `agent-fun/bars-replay/v1` on stdin/stdout).
- `LICENSE` — MIT.

## Run

The bot is graded by the make.fun harness on a frozen 24-hour dev window of
1-minute CBBTC bars; only entries with a dev net PnL above $0 race the live
24-hour window.
