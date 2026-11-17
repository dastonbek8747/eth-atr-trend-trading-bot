# ETH ATR Trend Pullback Bot

> An automated trading bot for ETHUSDT that uses an ATR trend-pullback strategy. Streamlit dashboard plus ccxt. Sandbox and demo only.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)


## Strategy

1. Determine trend direction with a moving average.
2. Measure volatility with ATR (Average True Range).
3. Enter on a pullback toward the trend, with the stop placed at an ATR multiple.
4. Exit on a take-profit target or a trailing stop.

## Features

- Streamlit dashboard with live price and indicators.
- ccxt exchange layer.
- Sandbox/demo mode by default.

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit |
| Exchange | ccxt |
| Data | pandas |
| Indicators | ATR, moving averages |

## Quick Start

```bash
git clone https://github.com/dastonbek8747/eth-atr-trend-trading-bot.git
cd eth-atr-trend-trading-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # add API keys
streamlit run main.py
```

## Disclaimer

Educational project. Not financial advice. Run it on a testnet first. The API keys that were once committed here are no longer valid; always rotate any key you ever pushed.

## License

MIT © 2026 Doston Sultonov.
