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
    def __init__(self):
        EClient.__init__(self, self)
        self.order_filled_event = threading.Event()

    def tickPrice(self, reqId, tickType, price, attrib):
        #tickType 1 gives the bid price
        if tickType == 1:
            print('The current bid price is: ', price)
        #tickType 2 gives the ask price
        if tickType == 2:
            print('The current ask price is: ', price)
    
    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice, permId,
                    parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        print(f"Order {orderId}: {status}, Filled: {filled}, Remaining: {remaining}")
        if status == "Filled":
            self.order_filled_event.set()

class ForexBot():
    ib = None
    reqId = 1
    orderId = 1

    def __init__(self):
        #Connect to IB on init
        self.ib = IBapi()
        ib_thread = threading.Thread(target=self.connect, daemon=True)
        ib_thread.start()
        #Allow server to connect
        time.sleep(1)

    def connect(self):
        self.ib.connect("127.0.0.1", 7497, 1)
        self.ib.run()
    
    def disconnect(self):
        self.ib.disconnect()

    def get_market_data(self):        
        #Define contract type
        contract = Contract()
        symbol = "EUR"
        currency = "USD"
        contract.symbol = symbol
        contract.currency = currency
        contract.secType = "CASH"
        contract.exchange = "IDEALPRO"

        #Assign reqId and increment for future requests
        reqId = self.reqId
        self.reqId += 1

        #Set delayed market data (3) or real time (1)
        self.ib.reqMarketDataType(3)

        print("Displaying market data stream for " + symbol + "/" + currency + ": \n")
        #Request market data
        self.ib.reqMktData(
            reqId=reqId,
            contract=contract,
            genericTickList="",
            snapshot=False,
            regulatorySnapshot=False, #False = streaming, True = single
            mktDataOptions=[]
        )

        input("Press any key to stop market data stream \n")
        print('Stopping market data stream for ' + symbol + "/" + currency + ". \n")
        self.stop_market_data(reqId)

    def stop_market_data(self, reqId):
        self.ib.cancelMktData(reqId)

    def place_buy_order(self, quantity=1):
        #Define order type
        order = Order()
        order.orderType = "MKT" # or LMT
        order.action = "BUY"
        order.totalQuantity = quantity

        #Define contract type
        contract = Contract()
        symbol = "EUR"
        currency = "USD"
        contract.symbol = symbol
        contract.currency = currency
        contract.secType = "CASH"
        contract.exchange = "IDEALPRO"

        #Assign orderId and increment for future requests
        orderId = self.orderId
        self.orderId += 1

        self.ib.placeOrder(orderId, contract, order)

        print("Waiting for order to fill...")
        self.ib.order_filled_event.wait(timeout=30)
        if self.ib.order_filled_event.is_set():
            print("Order was filled")
        else:
            print("Timed out waiting for order fill")


bot = ForexBot()
print("Get real time market data: \n")
bot.get_market_data()
# print("Place an order: \n")
# bot.place_buy_order(10)
