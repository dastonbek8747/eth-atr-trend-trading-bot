import ccxt

exchange = ccxt.binance({
    'apiKey': 'hVny8GTa0xkURqVsP0MsCDo9e0BgToTfHpmFn8kX3JfycBliJxpiJtZkW7IcqjV7',
    'secret': '6fLVTFuYrKDYccyzd5jhKPyzsReTwvjpOAOB0IxGXsJuRXsjIhqqpv2eMaPUdecd',
    'enableRateLimit': True,
})
exchange.set_sandbox_mode(True)
balance = exchange.fetch_balance()

usdt_balance = balance['total'].get('USDT', 0)
rounded_usdt_balance = round(usdt_balance, 0)

print(f"USDT balans: {rounded_usdt_balance}")
