# Forex Trading Bot

## Introduction
In this project I explored the intersection of quantitative finance and software development. I created a trading bot using [Interactive Brokers' (IB) Python API](https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/#api-introduction) to stream real-time, tick-by-tick forex market data and execute orders on a simulated trading account though both their Trader Work Station (TWS) and their headless application, IB Gateway. 

## Amazon Web Services
I tested the perpetuality of the trading bot by deploying it headlessly on an Amazon Web Services (AWS) Elastic Compute Cloud (EC2). The IB Gateway application has many requirements, such as a GUI interface for login and hosting, as well as a daiy reboot. To automatically handle these prerequisites, I created a shell script which creates a X Virtual Frame Buffer to simulate an interface and leverages the [Interactive Brokers Controller (IBC)](https://github.com/IbcAlpha/IBC?tab=readme-ov-file) utility to fill in my credentials. After that, I configured a cron job run the script daily. 

## Strategy
I currently implemented a Moving Average Convergence Divergence (MACD) strategy which is recalculated with even new bid-ask tick. I look forward to running the bot over the span of the next few weeks and record its results. I plan on coming back to this project in the future and implementing more complex strategies related to arbitrage and spread-capture!
