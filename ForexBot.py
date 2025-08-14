import ibapi
import threading
import time
import pytz
import csv
import pandas as pd
from datetime import datetime as dt, timedelta

#Handles outgoing data
from ibapi.client import EClient
#Handles incoming data
from ibapi.wrapper import EWrapper
#To request data
from ibapi.contract import Contract
#To submit orders
from ibapi.order import *
#To cancel orders
from ibapi.order_cancel import OrderCancel

#Class for Interactive Brokers Connection
#Must override function names from EWrapper to process incoming data
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

class ForexBot():
    reqId = 1
    orderId = 1
    symbol = "EUR"
    currency = "USD"
    ticker = "EUR/USD"

    def __init__(self):
        #Define event threads
        self.connected_event = threading.Event()
        self.data_received_event = threading.Event()
        self.order_filled_event = threading.Event()

        #Connect to IB on init
        self.ib = IBapi(self)
        
        ib_thread = threading.Thread(target=self.connect, daemon=True)
        ib_thread.start()
        #Wait for server to connect
        self.connected_event.wait(timeout=10)
    
        if not self.connected_event.is_set():
            print("Timed out waiting to connect")
            exit()

        #Define contract
        self.contract = Contract()
        self.contract.symbol = self.symbol
        self.contract.currency = self.currency
        self.contract.secType = "CASH"
        self.contract.exchange = "IDEALPRO"

        #Note start time
        self.startTime = dt.now().astimezone(pytz.utc)

    def connect(self):
        self.ib.connect("127.0.0.1", 7497, 1)
        self.ib.run()
    
    def confirm_connection(self, orderId):
        self.orderId = orderId
        self.connected_event.set()

    def disconnect(self):
        self.ib.disconnect()

    #Get historical data leading up to the start time
    def get_historical_data(self):
        endTime = self.startTime.strftime("%Y%m%d-%H:%M:%S")
        self.ib.reqHistoricalTicks(self.reqId, self.contract,  "", endTime, 20, "BID_ASK", 1, True, [])
        self.data_received_event.wait(timeout=10)
        
        if not self.data_received_event.is_set():
            print("Timed out waiting for data")
            exit()
            
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

    
    def get_market_data(self):        
        #Assign reqId and increment for future requests
        reqId = self.reqId
        self.reqId += 1

        #Set delayed market data (3) or real time (1)
        self.ib.reqMarketDataType(3)

        print("Displaying market data stream for " + self.ticker + ": \n")
        #Request market data
        self.ib.reqMktData(
            reqId=reqId,
            contract=self.contract,
            genericTickList="",
            snapshot=False,
            regulatorySnapshot=False, #False = streaming, True = single
            mktDataOptions=[]
        )

        input("Press any key to stop market data stream \n")
        print('Stopping market data stream for ' + self.ticker + ". \n")
        self.stop_market_data(reqId)
    
    def tick_price(self, reqId, tickType, price, attrib):
        #tickType 1 gives the bid price
        if tickType == 1:
            print('The current bid price is: ', price)
        #tickType 2 gives the ask price
        if tickType == 2:
            print('The current ask price is: ', price)

    def stop_market_data(self, reqId):
        self.ib.cancelMktData(reqId)

    def place_buy_order(self, quantity=1):
        #Define order type
        order = Order()
        order.orderType = "MKT" # or LMT
        order.action = "BUY"
        order.totalQuantity = quantity

        #Assign orderId and increment for future requests
        orderId = self.orderId
        self.orderId += 1

        self.ib.placeOrder(orderId, self.contract, order)

        print("Waiting for order to fill...")
        self.order_filled_event.wait(timeout=10)

        if self.order_filled_event.is_set():
            self.order_filled_event.clear()
            print("Order was filled")
        else:
            print("Timed out waiting for order fill")
            self.ib.cancelOrder(orderId, OrderCancel())

    def order_status(self, orderId, status, filled, remaining, avgFillPrice, permId,
                    parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        print(f"Order {orderId}: {status}, Filled: {filled}, Remaining: {remaining}")
        if status == "Filled":
            self.order_filled_event.set()

    def buy_for_day(self, quantity):
        iterations = 10 #Run from 11am EST - 3:30pm EST
        interval = 30 #Every half hour
        runTime = dt.now().astimezone(pytz.utc)
        endTime = runTime.replace(hour=19, minute=30, second=0, microsecond=0)

        #Sleep until 11am EST/3pm UTC before starting
        startTime = runTime.replace(hour=15, minute=0, second=0, microsecond=0)
        waitTime = (startTime - runTime).total_seconds()
        print(waitTime)
        if waitTime > 0:
            time.sleep(waitTime)

        #Create order log file
        timestamp = startTime.strftime("%Y%m%d-%H:%M:%S")
        fileName = f"OrderLog_{timestamp}.csv"
        with open(fileName, "a", newline="") as log:
            writer = csv.writer(log)
            writer.writerow(["Time", "Action", "Symbol", "Quantity"])

            for i in range(iterations):
                orderTime = dt.now().astimezone(pytz.utc).strftime("%Y%m%d-%H:%M:%S")
                if (orderTime - endTime).total_seconds() < 0:
                    print("End time reached")
                    exit()
                self.place_buy_order(quantity)

                writer.writerow([orderTime,"BUY", self.ticker, quantity])
                log.flush()

                nextTime = startTime + timedelta(minutes = (i + 1) * interval)
                sleepTime = (nextTime - dt.now().astimezone(pytz.utc)).total_seconds()
                if sleepTime > 0:
                    time.sleep(sleepTime)
        
bot = ForexBot()
print("Get historical data: \n")
bot.get_historical_data()
print("Get real time market data: \n")
bot.get_market_data()
print("Place an order: \n")
bot.place_buy_order(10)
print("Running script for 24 hours")
bot.buy_for_day(1)