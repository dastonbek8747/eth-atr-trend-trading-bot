"""Savdo signal mantiqiy ziddiyati regressiya testi (HIGH-004).

Muammo: `avto_savdo.py` da BUY/SELL signallari o'zaro ziddiyatli shartlar
tufayli HECH QACHON ishga tushmaydi.

BUY:
    shart 2: `close >= ema_20 -> return False`   (close < ema_20 kerak)
    shart 3: `close <= ema_20 -> return False`   (close > ema_20 kerak)
    -> bir vaqtda bajarilishi mumkin emas.

SELL ham xuddi shunday.

Tuzatishdan keyin: haqiqiy "pullback" holatida signal ishlashi kerak.
Test tuzatilgunga qadar YIQILADI.
"""
import os
import sys
import types
import unittest

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- ccxt stub: __init__ birjaga ulanmasligi uchun (signal logikasi sinovdan o'tadi) ---
if "ccxt" not in sys.modules:
    ccxt_stub = types.ModuleType("ccxt")

    class _FakeExchange:
        def __init__(self, *a, **k):
            pass

        def set_sandbox_mode(self, *a, **k):
            pass

        def fetch_balance(self, *a, **k):
            return {"total": {"USDT": 1000.0}}

    ccxt_stub.binance = lambda *a, **k: _FakeExchange()
    sys.modules["ccxt"] = ccxt_stub

sys.path.insert(0, REPO_ROOT)
from avto_savdo import ATRTrendPullbackBot  # noqa: E402


def make_bot():
    cfg = {
        "symbol": "ETHUSDT", "timeframe": "1h", "risk_per_trade": 1.0,
        "account_size": 1000.0, "is_testnet": True, "ema_fast": 20, "ema_slow": 50,
        "atr_period": 14, "sl_atr_multiplier": 2.0, "rr_ratio": 2.0,
        "max_trades_per_day": 2, "max_daily_loss_pct": 2.5, "use_session_filter": False,
        "rsi_period": 14, "rsi_filter_min": 45, "rsi_filter_max": 65,
    }
    bot = ATRTrendPullbackBot(cfg)
    bot.use_session_filter = False
    return bot


def bullish_pullback_df():
    """Ko'tarilish trendi; oxirgi shamda pastki soya EMA20 dan pastga tegdi,
    yopilish EMA20 dan yuqoriga qaytdi (klassik pullback-rejection)."""
    n = 60
    close = np.linspace(100, 130, n)
    df = pd.DataFrame({
        "open": close - 0.2, "high": close + 0.5,
        "low": close - 1.5, "close": close, "volume": 1.0,
    })
    bot = make_bot()
    df = bot.calculate_indicators(df)
    last = df.index[-1]
    df.loc[last, "close"] = 100.0
    df.loc[last, "open"] = 99.5
    df.loc[last, "low"] = 97.0      # EMA20 (99) dan pastga tegdi -> pullback
    df.loc[last, "high"] = 100.5
    df.loc[last, "ema_20"] = 99.0   # close (100) > ema_20 (99)
    df.loc[last, "ema_50"] = 95.0   # ema_20 > ema_50 (ko'tarilish trendi)
    df.loc[last, "rsi"] = 55.0
    df.loc[last, "atr"] = 2.0
    return bot, df


def bearish_pullback_df():
    """Pasayish trendi; oxirgi shamda yuqori soya EMA20 dan yuqoriga tegdi,
    yopilish EMA20 dan pastga qaytdi."""
    n = 60
    close = np.linspace(130, 100, n)
    df = pd.DataFrame({
        "open": close + 0.2, "high": close + 1.5,
        "low": close - 0.5, "close": close, "volume": 1.0,
    })
    bot = make_bot()
    df = bot.calculate_indicators(df)
    last = df.index[-1]
    df.loc[last, "close"] = 100.0
    df.loc[last, "open"] = 100.5
    df.loc[last, "high"] = 103.0    # EMA20 (101) dan yuqoriga tegdi -> pullback
    df.loc[last, "low"] = 99.5
    df.loc[last, "ema_20"] = 101.0  # close (100) < ema_20 (101)
    df.loc[last, "ema_50"] = 105.0  # ema_20 < ema_50 (pasayish trendi)
    df.loc[last, "rsi"] = 45.0
    df.loc[last, "atr"] = 2.0
    return bot, df


class SignalLogicTest(unittest.TestCase):
    def test_buy_signal_fires_on_valid_pullback(self):
        bot, df = bullish_pullback_df()
        last = df.iloc[-1]
        self.assertLess(last["low"], last["ema_20"], "test sharti: low < ema_20")
        self.assertGreater(last["close"], last["ema_20"], "test sharti: close > ema_20")
        self.assertTrue(
            bot.check_buy_signal(df),
            "Haqiqiy pullback holatida BUY signal ishga tushmadi "
            "(shartlar o'zaro ziddiyatli)",
        )

    def test_sell_signal_fires_on_valid_pullback(self):
        bot, df = bearish_pullback_df()
        last = df.iloc[-1]
        self.assertGreater(last["high"], last["ema_20"], "test sharti: high > ema_20")
        self.assertLess(last["close"], last["ema_20"], "test sharti: close < ema_20")
        self.assertTrue(
            bot.check_sell_signal(df),
            "Haqiqiy pullback holatida SELL signal ishga tushmadi "
            "(shartlar o'zaro ziddiyatli)",
        )


if __name__ == "__main__":
    unittest.main()
