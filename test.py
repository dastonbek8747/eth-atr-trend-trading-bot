import os

import ccxt
from dotenv import load_dotenv

load_dotenv()

exchange = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY', ''),
    'secret': os.getenv('BINANCE_API_SECRET', ''),
    'enableRateLimit': True,
})
exchange.set_sandbox_mode(True)
balance = exchange.fetch_balance()

usdt_balance = balance['total'].get('USDT', 0)
rounded_usdt_balance = round(usdt_balance, 0)

print(f"USDT balans: {rounded_usdt_balance}")
