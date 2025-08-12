#!/bin/bash

PIDS=$(ps aux | grep -i "ibgateway" | grep -v grep | awk '{print $2}')
if [ -n "$PIDS" ]; then
    kill $PIDS
fi

XTERM_PIDS=$(ps aux | grep -i "xterm -T IBC" | grep -v grep | awk '{print $2}')
if [ -n "$XTERM_PIDS" ]; then
    kill $XTERM_PIDS
fi

XVFB_PIDS=$(ps aux | grep -i "Xvfb :99" | grep -v grep | awk '{print $2}')
if [ -n "$XVFB_PIDS" ]; then
    kill $XVFB_PIDS
fi