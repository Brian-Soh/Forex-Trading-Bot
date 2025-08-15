#!/bin/bash

DISPLAY_NUM=99
LOCK_FILE="/tmp/.X${DISPLAY_NUM}-lock"

if [ -f "$LOCK_FILE" ]; then
  LOCK_PID=$(cat "$LOCK_FILE")
  
  if ps -p $LOCK_PID > /dev/null 2>&1; then
    export DISPLAY=:$DISPLAY_NUM
  else
    rm -f "$LOCK_FILE"
    Xvfb :${DISPLAY_NUM} -screen 0 1024x768x24 &
    export DISPLAY=:$DISPLAY_NUM
  fi
else
  Xvfb :${DISPLAY_NUM} -screen 0 1024x768x24 &
  export DISPLAY=:$DISPLAY_NUM
fi

echo "Running IB Gateway"
/opt/ibc/gatewaystart.sh &