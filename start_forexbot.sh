#!/bin/bash

IB_PIDS=$(ps aux | grep -i "ibgateway" | grep -v grep | awk '{print $2}')
if ! [ -n "$IB_PIDS" ]; then
    echo "IB Gateway not running"
    exit 1
fi

XTERM_PIDS=$(ps aux | grep -i "xterm -T IBC" | grep -v grep | awk '{print $2}')
if ! [ -n "$XTERM_PIDS" ]; then
    echo "IB Controller not running"
    exit 1
fi

XVFB_PIDS=$(ps aux | grep -i "Xvfb :99" | grep -v grep | awk '{print $2}')
if ! [ -n "$XVFB_PIDS" ]; then
    echo "Xvfb not running"
    exit 1
fi

echo "Running Forex Bot"
nohup python3 /home/ubuntu/Downloads/Forex-Trading-Bot/forex_bot.py &
