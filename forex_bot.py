import ibapi
import threading
import time
import pytz
import csv
import pandas as pd
from datetime import datetime as dt, timedelta

# Handles outgoing data
from ibapi.client import EClient
# Handles incoming data
from ibapi.wrapper import EWrapper
# To request data
from ibapi.contract import Contract
# To submit orders
from ibapi.order import *
# To cancel orders
from ibapi.order_cancel import OrderCancel

# Class for Interactive Brokers Connection
# Must override function names from EWrapper to process incoming data
class IBapi(EWrapper, EClient):
    def __init__(self, bot_ref):
        EClient.__init__(self, self)
        self.bot = bot_ref

    def nextValidId(self, orderId):
        self.bot.confirm_connection(orderId)

    def tickPrice(self, reqId, tickType, price, attrib):
        self.bot.tick_price(reqId, tickType, price, attrib)

    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice, permId,
                    parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        self.bot.order_status(orderId, status, filled, remaining, avgFillPrice, permId,
                    parentId, lastFillPrice, clientId, whyHeld, mktCapPrice)

    def historicalTicksBidAsk(self, reqId, ticks, done):
        self.bot.historical_ticks_bid_ask(reqId, ticks, done)

    def openOrder(self, orderId, contract, order, orderState):
        self.bot.record_open_order(orderId, contract, order, orderState)

class ForexBot():
    def __init__(self, symbol="EUR", currency="USD"):
        # Define Fields
        self.reqId = 1
        self.orderId = 1
        self.symbol = symbol
        self.currency = currency
        self.ticker = f"{symbol}/{currency}"
        self.order_events = {} # Create new threads for each order

        # Define thread locks and event threads
        self.reqid_lock = threading.Lock()
        self.orderid_lock = threading.Lock()
        self.connected_event = threading.Event()
        self.data_received_event = threading.Event()

        # Connect to IB on init
        self.ib = IBapi(self)
        
        ib_thread = threading.Thread(target=self.connect, daemon=True)
        ib_thread.start()
        # Wait for server to connect
        if not self.connected_event.wait(timeout=10):
            raise TimeoutError("Timed out waiting to connect")

        # Define contract
        self.contract = Contract()
        self.contract.symbol = self.symbol
        self.contract.currency = self.currency
        self.contract.secType = "CASH"
        self.contract.exchange = "IDEALPRO"

        # Note start time
        self.startTime = dt.now().astimezone(pytz.utc)

        self.openOrders = set()

        # MACD Settings
        self.last_ask = None
        self.last_bid = None
        self.ema_short = None
        self.ema_long = None
        self.signal = None
        self.alpha_short = 2 / (12 + 1)
        self.alpha_long = 2 / (26 + 1)
        self.alpha_signal = 2 / (9 + 1)

        # Crossover control
        self.last_diff = None        # previous (macd - signal)
        self.last_side = None        # last traded side to prevent repeats
        self.last_trade_ts = 0.0
        self.cooldown = 2.0          # minimum seconds between trades
        self.diff_eps = 1e-5         # deadband to ignore tiny jitters

    def connect(self):
        self.ib.connect("127.0.0.1", 7497, 1)
        self.ib.run()
    
    def confirm_connection(self, orderId):
        with self.orderid_lock:
            self.orderId = orderId
        self.connected_event.set()

    # Get historical data leading up to the start time
    def get_historical_data(self):
        endTime = self.startTime.strftime("%Y%m%d-%H:%M:%S")
        
        with self.reqid_lock:
            reqId = self.reqId
            self.reqId += 1
        self.ib.reqHistoricalTicks(reqId, self.contract,  "", endTime, 20, "BID_ASK", 1, True, [])
        
        if not self.data_received_event.wait(timeout=10):
            raise TimeoutError("Timed out waiting for data")
            
        self.data_received_event.clear()
        input("Press any key to continue \n")

    def historical_ticks_bid_ask(self, reqId, ticks, done):
        data = [{
            "time": pd.to_datetime(t.time, unit="s", utc=True).strftime("%Y%m%d-%H:%M:%S"),
            "bid": t.priceBid,
            "ask": t.priceAsk,
            "bidSize": t.sizeBid,
            "askSize": t.sizeAsk
        } for t in ticks]

        self.historicalData = pd.DataFrame(data)
        self.historicalData.set_index("time", inplace=True)

        print(self.historicalData)
        self.data_received_event.set()
    
    def run_strategy(self, manual=True):        

        with self.reqid_lock:
            reqId = self.reqId
            self.reqId += 1

        # Set delayed market data (3) or real time (1)
        self.ib.reqMarketDataType(1)

        print("Running strategy for " + self.ticker + ": \n")
        # Request market data
        self.ib.reqMktData(
            reqId=reqId,
            contract=self.contract,
            genericTickList="",
            snapshot=False,
            regulatorySnapshot=False, # False = streaming, True = single
            mktDataOptions=[]
        )

        if manual:
            input("Press any key to stop strategy \n")
            print('Stopping strategy for ' + self.ticker + ". \n")
            self.stop_market_data(reqId)
        else:
            return
    
    def tick_price(self, reqId, tickType, price, attrib):
        # tickType 1 gives the bid price
        if tickType == 1:
            print('The current bid price is: ', price)
            self.last_bid = price
        # tickType 2 gives the ask price
        elif tickType == 2:
            print('The current ask price is: ', price)
            self.last_ask = price

        if self.last_bid is not None and self.last_ask is not None:
            mid = (self.last_bid + self.last_ask) / 2.0
            self.last_mid = mid
            self.update_macd(mid)
            self.last_bid = self.last_ask = None

    def update_macd(self, mid):
            
        if self.ema_short is None:
            self.ema_short = self.ema_long = self.signal = mid
            self.last_diff = 0.0
            return
        
        # EMA updates
        self.ema_short = (mid - self.ema_short) * self.alpha_short + self.ema_short
        self.ema_long  = (mid - self.ema_long)  * self.alpha_long  + self.ema_long
        macd = self.ema_short - self.ema_long
        self.signal = (macd - self.signal) * self.alpha_signal + self.signal
        diff = macd - self.signal

        print(diff)

        # Trade ONLY on zero-cross with deadband and cooldown
        now = time.time()
        crossed_up   = self.last_diff <= -self.diff_eps and diff >=  self.diff_eps
        crossed_down = self.last_diff >=  self.diff_eps and diff <= -self.diff_eps

        if (now - self.last_trade_ts) >= self.cooldown:
            if crossed_up and self.last_side != "BUY":
                print(f"MACD cross↑ → BUY | macd={macd:.6f} signal={self.signal:.6f}")
                self.place_market_order("BUY", 1)
                self.last_trade_ts = now
                self.last_side = "BUY"
            elif crossed_down and self.last_side != "SELL":
                print(f"MACD cross↓ → SELL | macd={macd:.6f} signal={self.signal:.6f}")
                self.place_market_order("SELL", 1)
                self.last_trade_ts = now
                self.last_side = "SELL"

        self.last_diff = diff

    def stop_market_data(self, reqId):
        self.ib.cancelMktData(reqId)

    def place_market_order(self, action="BUY", quantity=1):
        # Define order type
        order = Order()
        order.orderType = "MKT"
        order.action = action
        order.totalQuantity = quantity

        with self.orderid_lock:
            orderId = self.orderId
            self.orderId += 1

        evt = threading.Event()
        self.order_events[orderId] = evt

        with open(self.fileName, "a", newline="") as log:
            writer = csv.writer(log)
            timeNow = dt.now().astimezone(pytz.utc)
            orderTime = timeNow.strftime("%Y%m%d-%H:%M:%S")
            writer.writerow([orderTime, "BUY", self.ticker, quantity])

        self.ib.placeOrder(orderId, self.contract, order)

        threading.Thread(
            target=self._await_fill_or_timeout,
            args=(orderId, evt),
            daemon=True
        ).start()

    def _await_fill_or_timeout(self, orderId, evt, timeout=10):
        print(f"Waiting for order {orderId} to fill")
        if evt.wait(timeout=timeout):
            print(f"Order {orderId} was filled")
        else:
            print(f"Timeout waiting for order {orderId}; attempting cancel")
            try:
                self.ib.cancelOrder(orderId, OrderCancel())
            except Exception as e:
                print(f"Cancel error for {orderId}: {e}")

        self.openOrders.discard(orderId)
        self.order_events.pop(orderId, None)

    def order_status(self, orderId, status, filled, remaining, avgFillPrice, permId,
                    parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        print(f"Order {orderId}: {status}, Filled: {filled}, Remaining: {remaining}")

        if hasattr(self, "cancelOrderTracker"):
            self.cancelOrderTracker(orderId, status)
        if status == "Filled":
            evt = self.order_events.get(orderId)
            if evt:
                evt.set()

    def buy_for_day(self, quantity):
        hours = 24
        startTime = dt.now().astimezone(pytz.utc)
        timestamp = startTime.strftime("%Y%m%d-%H:%M:%S")
        endTime = startTime + timedelta(hours=hours)
        
        self.fileName = f"./order_logs/OrderLog_{timestamp}.csv"
        with open(self.fileName, "a", newline="") as log:
            writer = csv.writer(log)
            writer.writerow(["Time", "Action", "Symbol", "Quantity"])
            log.flush()

        self.run_strategy(False)

        print(f"Running strategy for 24h")

        time.sleep(hours * 60 * 60)

    def buy_nyse_hours(self, quantity):
        runTime = dt.now().astimezone(pytz.utc)
        endTime = runTime.replace(hour=19, minute=30, second=0, microsecond=0)

        # Sleep until 11am EST/3pm UTC before starting
        startTime = runTime.replace(hour=15, minute=0, second=0, microsecond=0)
        waitTime = (startTime - runTime).total_seconds()

        print(waitTime)
        if waitTime > 0:
            time.sleep(waitTime)

        # Create order log file
        timestamp = startTime.strftime("%Y%m%d-%H:%M:%S")
        fileName = f"./order_logs/OrderLog_{timestamp}.csv"
        with open(fileName, "a", newline="") as log:
            writer = csv.writer(log)
            writer.writerow(["Time", "Action", "Symbol", "Quantity"])
                
        self.run_strategy(False)
        print(f"Running strategy")

        sleepTime = (endTime - dt.now()).seconds()

        time.sleep(sleepTime)
    
    def disconnect(self):
        toCancel = set(self.openOrders)
        
        if toCancel:
            all_orders_closed_event = threading.Event()

            def cancelTracker(orderId, status):
                if orderId in toCancel and status in ("Cancelled", "ApiCancelled", "Filled"):
                    toCancel.remove(orderId)
                    if not toCancel:
                        all_orders_closed_event.set()

            self.cancelOrderTracker = cancelTracker

            print(f"Canceling {len(toCancel)} open order(s): {list(toCancel)}")
            for id in toCancel:
                try:
                    self.ib.cancelOrder(id, OrderCancel())
                except Exception as e:
                    print(f"Failed to cancel order {id}: {e}")
            all_orders_closed_event.wait(timeout=10)
            
            if not all_orders_closed_event.is_set():
                print("Failed to cancel open orders")

        self.ib.disconnect()

    def record_open_order(self, orderId, contract, order, orderState):
        self.openOrders.add(orderId)

bot = ForexBot()
print("Get historical data: \n")
bot.get_historical_data()
# print("Run MACD strategy \n")
# bot.run_strategy()
# print("Place an order: \n")
# bot.place_market_order("BUY", 10)
print("Running script from 11am EST - 3:30 pm PST")
bot.buy_nyse_hours(1)
# print("Running script for 24 hours")
# bot.buy_for_day(1)
print("Disconnecting from Interactive Brokers")
bot.disconnect()
