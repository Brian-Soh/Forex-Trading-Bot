import ibapi
import importlib
import signal
import sys
import threading
import time
import pytz
import csv
import pandas as pd
from datetime import datetime as dt

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

    def error(self, reqId, *args):
        # Newer ibapi builds pass errorTime before errorCode, older ones don't
        code, msg = args[1:3] if isinstance(args[1], int) else args[:2]
        self.bot.on_error(reqId, code, msg)

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

def load_strategy(name):
    # A strategy is a file in strategies/ that exports its class as Strategy
    return importlib.import_module(f"strategies.{name}").Strategy()

class ForexBot():
    def __init__(self, strategy, symbol="EUR", currency="USD"):
        # Define Fields
        self.strategy = strategy
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
        self.stopping = threading.Event()
        self.mktReqId = None         # live market data stream, re-requested after a reconnect

        # What the bot itself has traded, for P&L and for closing out on shutdown
        self.quantity = 1
        self.position = 0.0
        self.cash = 0.0
        self.pending = {}            # orderId -> action, until the order fills or is cancelled

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
        self.fileName = f"./order_logs/OrderLog_{self.startTime.strftime('%Y%m%d-%H:%M:%S')}.csv"

        self.openOrders = set()

        self.last_ask = None
        self.last_bid = None

    def connect(self):
        # IB Gateway restarts daily, so keep reconnecting until disconnect() is called
        while not self.stopping.is_set():
            try:
                self.ib.connect("127.0.0.1", 4002, 1)
                self.ib.run()
            except Exception as e:
                print(f"IB connection error: {e}")
            if not self.stopping.wait(10):
                print("Disconnected from IB, reconnecting")
    
    def confirm_connection(self, orderId):
        with self.orderid_lock:
            self.orderId = orderId
        self.connected_event.set()
        # Does nothing on the first connect, restores the stream after a reconnect
        self.subscribe()

    def on_error(self, reqId, code, msg):
        print(f"IB error {code} (id {reqId}): {msg}")
        # 1101 = link to IB is back but market data subscriptions were lost
        if code == 1101:
            self.subscribe()

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
            self.mktReqId = self.reqId
            self.reqId += 1

        print("Running strategy for " + self.ticker + ": \n")
        self.subscribe()

        if manual:
            input("Press any key to stop strategy \n")
            print('Stopping strategy for ' + self.ticker + ". \n")
            self.stop_market_data()
        else:
            return

    def subscribe(self):
        if self.mktReqId is None:
            return

        # Set delayed market data (3) or real time (1)
        self.ib.reqMarketDataType(1)

        # Request market data
        self.ib.reqMktData(
            reqId=self.mktReqId,
            contract=self.contract,
            genericTickList="",
            snapshot=False,
            regulatorySnapshot=False, # False = streaming, True = single
            mktDataOptions=[]
        )
    
    def tick_price(self, reqId, tickType, price, attrib):
        # No new trades once shutdown has started
        if self.stopping.is_set():
            return

        # tickType 1 gives the bid price
        if tickType == 1:
            print('The current bid price is: ', price)
            self.last_bid = price
        # tickType 2 gives the ask price
        elif tickType == 2:
            print('The current ask price is: ', price)
            self.last_ask = price

        if self.last_bid is not None and self.last_ask is not None:
            action = self.strategy.on_tick(self.last_bid, self.last_ask)
            self.last_bid = self.last_ask = None
            # Anything but BUY would be booked as a sell by record_fill, so reject typos here
            if action in ("BUY", "SELL"):
                self.place_market_order(action, self.quantity)
            elif action is not None:
                print(f"Ignoring invalid signal {action!r} from strategy")

    def stop_market_data(self):
        if self.mktReqId is not None:
            self.ib.cancelMktData(self.mktReqId)
            self.mktReqId = None

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
        self.pending[orderId] = action

        self.ib.placeOrder(orderId, self.contract, order)

        threading.Thread(
            target=self._await_fill_or_timeout,
            args=(orderId, evt),
            daemon=True
        ).start()
        return evt

    # Log a fill and update the bot's own position and P&L
    def record_fill(self, action, quantity, price):
        signed = quantity if action == "BUY" else -quantity
        self.position += signed
        self.cash -= signed * price
        # shortcut: P&L leaves out commissions, add IB's commissionReport callback when fees matter
        pnl = self.cash + self.position * price

        with open(self.fileName, "a", newline="") as log:
            writer = csv.writer(log)
            if log.tell() == 0:
                writer.writerow(["Time", "Action", "Symbol", "Quantity", "Price", "Position", "PnL"])
            fillTime = dt.now().astimezone(pytz.utc).strftime("%Y%m%d-%H:%M:%S")
            writer.writerow([fillTime, action, self.ticker, quantity, price, self.position, round(pnl, 5)])

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

        # IB repeats final statuses, so pop to count each order once. A cancelled order can be part-filled.
        if status in ("Filled", "Cancelled", "ApiCancelled"):
            action = self.pending.pop(orderId, None)
            if action and filled:
                self.record_fill(action, float(filled), avgFillPrice)

        if hasattr(self, "cancelOrderTracker"):
            self.cancelOrderTracker(orderId, status)
        if status == "Filled":
            evt = self.order_events.get(orderId)
            if evt:
                evt.set()

    def buy_for_day(self, quantity):
        hours = 24
        self.quantity = quantity

        self.run_strategy(False)

        print(f"Running strategy for 24h")

        time.sleep(hours * 60 * 60)

    def buy_nyse_hours(self, quantity):
        self.quantity = quantity
        # New York time, so the window stays right when daylight saving changes
        runTime = dt.now(pytz.timezone("America/New_York"))
        endTime = runTime.replace(hour=15, minute=30, second=0, microsecond=0)

        # Sleep until 11am New York time before starting
        startTime = runTime.replace(hour=11, minute=0, second=0, microsecond=0)
        waitTime = (startTime - runTime).total_seconds()

        print(waitTime)
        if waitTime > 0:
            time.sleep(waitTime)

        self.run_strategy(False)
        print(f"Running strategy")

        sleepTime = (endTime - dt.now(pytz.utc)).total_seconds()
        if sleepTime > 0:
            time.sleep(sleepTime)
    
    def disconnect(self):
        self.stopping.set()
        self.stop_market_data()

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

        # Close whatever the bot itself opened so no position is left on the account
        if self.position:
            action = "SELL" if self.position > 0 else "BUY"
            print(f"Closing position of {self.position} {self.ticker}")
            if not self.place_market_order(action, abs(self.position)).wait(timeout=10):
                print(f"Failed to close position of {self.position} {self.ticker}, close it by hand")
        if not self.position:
            print(f"P&L before commissions: {self.cash:.5f} {self.currency}")

        self.ib.disconnect()

    def record_open_order(self, orderId, contract, order, orderState):
        self.openOrders.add(orderId)

if __name__ == "__main__":
    # Makes `kill` run the cleanup in `finally` too
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    # Loaded before connecting so a mistyped name fails straight away
    bot = ForexBot(load_strategy(sys.argv[1] if len(sys.argv) > 1 else "macd"))
    try:
        # print("Get historical data: \n")
        # bot.get_historical_data()
        # print("Run strategy \n")
        # bot.run_strategy()
        # print("Place an order: \n")
        # bot.place_market_order("BUY", 10)
        # print("Running script from 11am EST - 3:30 pm EST")
        # bot.buy_nyse_hours(1)
        print("Running script for 24 hours")
        bot.buy_for_day(1)
    finally:
        print("Disconnecting from Interactive Brokers")
        bot.disconnect()
