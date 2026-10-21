import pandas as pd
import yfinance as yf

TICKER = "AAPL"

ticker = yf.Ticker(TICKER)
info = ticker.info
fast = ticker.fast_info

company_name = info.get("longName") or info.get("shortName") or TICKER
current_price = fast.last_price
previous_close = fast.previous_close
change_rate = (current_price - previous_close) / previous_close * 100

print(f"회사명: {company_name}")
currency = fast.currency
print(f"현재가: {current_price:,.2f} {currency}")
print(f"전일대비등락률: {change_rate:+.2f}%")

history = ticker.history(period="1mo")
print("\n최근 1개월 일별 데이터 (처음 5행)")
with pd.option_context("display.max_columns", None, "display.width", None):
    print(history.head())
