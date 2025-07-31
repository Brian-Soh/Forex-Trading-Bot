import ibapi
import threading
import time

#Handles outgoing data
from ibapi.client import EClient
#Handles incoming data
from ibapi.wrapper import EWrapper
#To request data
from ibapi.contract import Contract
#To submit orders
from ibapi.order import *

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

class ForexBot():
    ib = None
    reqId = 1
    orderId = 1
    symbol = "EUR"
    currency = "USD"
    ticker = "EUR/USD"
    contract = Contract()

    def __init__(self):
        #Define event threads
        self.connected_event = threading.Event()
        self.order_filled_event = threading.Event()

        #Connect to IB on init
        self.ib = IBapi(self)
        
        ib_thread = threading.Thread(target=self.connect, daemon=True)
        ib_thread.start()
        #Wait for server to connect
        self.connected_event.wait(timeout=10)
        if not self.connected_event.is_set():
            print("Timed out waiting to connect")

        #Define contract
        self.contract.symbol = self.symbol
        self.contract.currency = self.currency
        self.contract.secType = "CASH"
        self.contract.exchange = "IDEALPRO"

    def connect(self):
        self.ib.connect("127.0.0.1", 7497, 1)
        self.ib.run()
    
    def confirm_connection(self, orderId):
        self.orderId = orderId
        self.connected_event.set()

    def disconnect(self):
        self.ib.disconnect()

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
        self.order_filled_event.wait(timeout=30)
        if self.order_filled_event.is_set():
            self.order_filled_event.clear()
            print("Order was filled")
        else:
            print("Timed out waiting for order fill")

    def order_status(self, orderId, status, filled, remaining, avgFillPrice, permId,
                    parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        print(f"Order {orderId}: {status}, Filled: {filled}, Remaining: {remaining}")
        if status == "Filled":
            self.order_filled_event.set()


bot = ForexBot()
print("Get real time market data: \n")
bot.get_market_data()
print("Place an order: \n")
bot.place_buy_order(10)
