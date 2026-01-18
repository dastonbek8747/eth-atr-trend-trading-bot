import ccxt

exchange = ccxt.binance({
    'apiKey': '***REMOVED-BINANCE-KEY***',
    'secret': '***REMOVED-BINANCE-SECRET***',
    'enableRateLimit': True,
})
exchange.set_sandbox_mode(True)
balance = exchange.fetch_balance()

usdt_balance = balance['total'].get('USDT', 0)
rounded_usdt_balance = round(usdt_balance, 0)

print(f"USDT balans: {rounded_usdt_balance}")
