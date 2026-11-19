# Forex Trading Bot

## Introduction
In this project I explored the intersection of quantitative finance and software development. I created a trading bot using [Interactive Brokers' (IB) Python API](https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/#api-introduction) to stream real-time, tick-by-tick forex market data and execute orders on a simulated trading account through both their Trader Work Station (TWS) and their headless application, IB Gateway.

## Amazon Web Services
I tested the perpetuality of the trading bot by deploying it headlessly on an Amazon Web Services (AWS) Elastic Compute Cloud (EC2). The IB Gateway application has many requirements, such as a GUI interface for login and hosting, as well as a daily reboot. To automatically handle these prerequisites, I created a shell script which creates a X Virtual Frame Buffer to simulate an interface and leverages the [Interactive Brokers Controller (IBC)](https://github.com/IbcAlpha/IBC?tab=readme-ov-file) utility to fill in my credentials. After that, I configured a cron job to run the script daily.

## Strategies
I refactored the bot so that strategies are plug and play. Each strategy lives in its own file under `strategies/` and exposes a class with an `on_tick(bid, ask)` method that returns `"BUY"`, `"SELL"`, or nothing. The engine streams quotes, asks the strategy what to do, and places market orders when it gets a signal. To try a different idea I only need to add a file and pass its name when I launch the bot.

I currently have two strategies. The first is Moving Average Convergence Divergence (MACD), which recalculates on every bid-ask tick and trades when the MACD line crosses its signal line. It is meant to follow momentum. The second is a mean reversion strategy, which waits for a short window of mid prices and fades moves that stretch too far from that average: buying when price looks unusually low and selling when it looks unusually high. I wanted a second strategy that behaves the opposite of MACD so I could compare trend-following and mean-reverting ideas on the same tick stream.

I launch a strategy like this (port `7497` is TWS paper; `4002` is IB Gateway paper, which my EC2 setup uses):

```bash
python forex_bot.py macd 7497
python forex_bot.py mean_reversion 7497
```

By default the bot trades 20000 EUR on EUR/USD, which matches IDEALPRO's usual minimum size so orders are more likely to fill. I also cap open exposure at two full order sizes and check Interactive Brokers for existing holdings on the pair, so a position I opened by hand in TWS still counts toward the limit. I look forward to running both strategies over longer windows and comparing their results. I still plan on coming back to more complex ideas related to arbitrage and spread-capture!

## Sample Instance
Here is a trade log of running the trading bot for 24 hours on the EUR/USD exchange.

<img width="353" height="214" alt="image" src="https://github.com/user-attachments/assets/1bd2704d-be77-4329-80c7-8c90a391b005" />

We can now analyze the charts of when the trades occurred through TradingView. Evidently, the MACD indicator proved successful in jumping on upward trends in most instances!

Trade 1:
<img width="421" height="469" alt="image" src="https://github.com/user-attachments/assets/135248a8-61bf-4bdd-b269-0037c4d8c5eb" />

Trade 2:
<img width="393" height="410" alt="image" src="https://github.com/user-attachments/assets/8835edea-7f1a-4784-8716-dba2468ee7fd" />

Trade 3
<img width="296" height="467" alt="image" src="https://github.com/user-attachments/assets/33dfc1b4-aefe-4b6a-bad4-43a55f70f62f" />

Trade 4
<img width="346" height="469" alt="image" src="https://github.com/user-attachments/assets/71c6c1b2-183d-4d53-8a12-2db5b77bc0c0" />
