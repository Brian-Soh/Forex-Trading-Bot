import ibapi
import threading
import time

#Handles outgoing data
from ibapi.client import EClient
#Handles incoming data
from ibapi.wrapper import EWrapper
#To request data
from ibapi.contract import Contract

class IBapi(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

    def tickPrice(self, reqId, tickType, price, attrib):
        #tickType 1 gives the bid price
        if tickType == 1:
            print('The current bid price is: ', price)
        #tickType 2 gives the ask price
        if tickType == 2:
            print('The current ask price is: ', price)

class ForexBot():
    ib = None
    reqId = 1
    def __init__(self):
        #Connect to IB on init
        self.ib = IBapi()
        ib_thread = threading.Thread(target=self.connect, daemon=True)
        ib_thread.start()
        #Allow server to connect
        time.sleep(1)

    def get_market_data(self):        
        #Create IB Contract Object
        contract = Contract()
        symbol = input("Enter the base currency you want to trade: ").upper()
        currency = input("Enter the quote currency you want to trade: ").upper()
        contract.symbol = symbol
        contract.secType = "CASH"
        contract.currency = currency
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

    def connect(self):
        self.ib.connect("127.0.0.1", 7497, 1)
        self.ib.run()
    
    def disconnect(self):
        self.ib.disconnect()

bot = ForexBot()
bot.get_market_data()
bot.disconnect()
