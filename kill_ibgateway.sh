#!/bin/bash

IB_PIDS=$(ps aux | grep -i "ibgateway" | grep -v grep | awk '{print $2}')
if [ -n "$IB_PIDS" ]; then
    echo "Killing IB Gateway process: $IB_PIDS"
    kill -9 $IB_PIDS
else
    echo "No IB Gateway process found."
fi

XTERM_PIDS=$(ps aux | grep -i "xterm -T IBC" | grep -v grep | awk '{print $2}')
if [ -n "$XTERM_PIDS" ]; then
    echo "Killing IBC launcher: $XTERM_PIDS"
    kill -9 $XTERM_PIDS
else
    echo "No IBC launcher found."
fi

XVFB_PIDS=$(ps aux | grep -i "Xvfb :99" | grep -v grep | awk '{print $2}')
if [ -n "$XVFB_PIDS" ]; then
    echo "Killing Xvfb :99 process: $XVFB_PIDS"
    kill -9 $XVFB_PIDS
else
    echo "No Xvfb :99 process found."
fi
