import os
from datetime import datetime, timedelta

from alpaca_trade_api import REST
from dotenv import load_dotenv
from lumibot.backtesting import YahooDataBacktesting
from lumibot.brokers import Alpaca
from lumibot.strategies import Strategy

from utils.finbert_util import estimate_sentiment

# from lumibot.traders import Trader


load_dotenv()

ALPACA_CREDS = {
    "API_KEY": os.getenv("API_KEY"),
    "API_SECRET": os.getenv("API_SECRET"),
    "PAPER": True,
}

STOCK_SYMBOL = "SPY"
CASH_AT_RISK = 0.5


class MLTrader(Strategy):
    def initialize(
        self, symbol: str = STOCK_SYMBOL, cash_at_risk: float = CASH_AT_RISK
    ):
        self.symbol = symbol
        self.sleeptime = "10M"
        self.last_trade = None
        self.cash_at_risk = cash_at_risk
        self.api = REST(
            base_url=os.getenv("BASE_URL"),
            key_id=ALPACA_CREDS["API_KEY"],
            secret_key=ALPACA_CREDS["API_SECRET"],
        )

    def position_sizing(self):
        cash = self.get_cash()
        last_price = self.get_last_price(self.symbol)
        quantity = round(cash * self.cash_at_risk / last_price, 0)
        return cash, last_price, quantity

    def get_dates(self):
        today = self.get_datetime()
        three_days_prior = today - timedelta(days=3)
        return today.strftime("%Y-%m-%d"), three_days_prior.strftime("%Y-%m-%d")

    def get_sentiment(self):
        today, three_days_prior = self.get_dates()
        news = self.api.get_news(self.symbol, start=three_days_prior, end=today)
        news = [ev.__dict__["_raw"]["headline"] for ev in news]

        probability, sentiment = estimate_sentiment(news=news)
        return probability, sentiment

    def on_trading_iteration(self):
        cash, last_price, quantity = self.position_sizing()
        probability, sentiment = self.get_sentiment()

        if cash > last_price:
            if sentiment == "positive" and probability > 0.999:
                if self.last_trade == "sell":
                    self.sell_all()
                order = self.create_order(
                    self.symbol,
                    quantity,
                    "buy",
                    type="bracket",
                    take_profit_price=last_price * 1.2,
                    stop_loss_price=last_price * 0.95,
                )
                self.submit_order(order=order)
                self.last_trade = "buy"
            elif sentiment == "negative" and probability > 0.999:
                if self.last_trade == "buy":
                    self.sell_all()
                order = self.create_order(
                    self.symbol,
                    quantity,
                    "sell",
                    type="bracket",
                    take_profit_price=last_price * 0.8,
                    stop_loss_price=last_price * 1.05,
                )
                self.submit_order(order=order)
                self.last_trade = "sell"


start_date = datetime(2025, 5, 1)
end_date = datetime(2025, 6, 13)

broker = Alpaca(ALPACA_CREDS)
strategy = MLTrader(
    name="mlstrat",
    broker=broker,
    parameters={"symbol": STOCK_SYMBOL, "cash_at_risk": CASH_AT_RISK},
)
strategy.backtest(
    YahooDataBacktesting,
    start_date,
    end_date,
    parameters={"symbol": STOCK_SYMBOL, "cash_at_risk": CASH_AT_RISK},
)

# # Run in real market or paper trading mode
# trader = Trader()
# trader.add_strategy(strategy)
# trader.run_all()
