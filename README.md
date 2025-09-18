# Forex Trading Bot

## Introduction
In this project I explored the intersection of quantitative finance and software development. I created a trading bot using [Interactive Brokers' (IB) Python API](https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/#api-introduction) to stream real-time, tick-by-tick forex market data and execute orders on a simulated trading account though both their Trader Work Station (TWS) and their headless application, IB Gateway. 

## Amazon Web Services
I tested the perpetuality of the trading bot by deploying it headlessly on an Amazon Web Services (AWS) Elastic Compute Cloud (EC2). The IB Gateway application has many requirements, such as a GUI interface for login and hosting, as well as a daiy reboot. To automatically handle these prerequisites, I created a shell script which creates a X Virtual Frame Buffer to simulate an interface and leverages the [Interactive Brokers Controller (IBC)](https://github.com/IbcAlpha/IBC?tab=readme-ov-file) utility to fill in my credentials. After that, I configured a cron job run the script daily. 

## Strategy
I implemented a Moving Average Convergence Divergence (MACD) strategy which is recalculated with even new bid-ask tick. I look forward to running the bot over the span of the next few weeks and record its results. I plan on coming back to this project in the future and implementing more complex strategies related to arbitrage and spread-capture!

## Sample Instance
Here is a trade log of running the trading bot for 24 hours on the EUR/USD exchange.

<img width="353" height="214" alt="image" src="https://github.com/user-attachments/assets/1bd2704d-be77-4329-80c7-8c90a391b005" />

We can now analyze the charts of when the trades occured through TradingView. Evidently, the MACD indicator proved successful in jumping on upward trends in most instances!

Trade 1:
<img width="421" height="469" alt="image" src="https://github.com/user-attachments/assets/135248a8-61bf-4bdd-b269-0037c4d8c5eb" />

Trade 2:
<img width="393" height="410" alt="image" src="https://github.com/user-attachments/assets/8835edea-7f1a-4784-8716-dba2468ee7fd" />

Trade 3
<img width="296" height="467" alt="image" src="https://github.com/user-attachments/assets/33dfc1b4-aefe-4b6a-bad4-43a55f70f62f" />

Trade 4
<img width="346" height="469" alt="image" src="https://github.com/user-attachments/assets/71c6c1b2-183d-4d53-8a12-2db5b77bc0c0" />

