import ccxt
import pandas as pd
import numpy as np
import requests
import logging
from datetime import datetime, timedelta
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class ATRTrendPullbackBot:
    """ATR Trend Pullback Strategy - ETHUSDT Binance Perpetual/Spot"""

    def __init__(self, config):
        self.config = config
        self.symbol = config['symbol']  # ETHUSDT
        self.timeframe = config['timeframe']  # M30 yoki H1
        self.risk_per_trade = config['risk_per_trade']  # 0.5% - 1%
        self.account_size = config['account_size']
        self.is_testnet = config['is_testnet']

        # EMA settings
        self.ema_fast = config['ema_fast']  # 20
        self.ema_slow = config['ema_slow']  # 50

        # ATR settings (ETH uchun yuqori volatility)
        self.atr_period = config['atr_period']  # 14
        self.sl_atr_multiplier = config['sl_atr_multiplier']  # 2.0 (XAUdan farq!)
        self.rr_ratio = config['rr_ratio']  # 2.0

        # Risk management
        self.max_trades_per_day = config['max_trades_per_day']  # 2
        self.max_daily_loss_pct = config['max_daily_loss_pct']  # 2-3%
        self.use_session_filter = config['use_session_filter']
        self.rsi_period = config['rsi_period']  # 14
        self.rsi_filter_min = config['rsi_filter_min']  # 45 (ETH uchun)
        self.rsi_filter_max = config['rsi_filter_max']  # 65

        # Telegram
        self.telegram_token = config.get('telegram_token', '')
        self.telegram_chat_id = config.get('telegram_chat_id', '')

        # Initialize exchange
        self.exchange = self._init_exchange(config)

        # State tracking
        self.is_running = False
        self.trades_history = []
        self.open_positions = []
        self.daily_trades_count = 0
        self.initial_balance = self.account_size
        self.daily_start_balance = self.initial_balance
        self.daily_loss = 0
        self.last_trade_time = None

        logging.info(f"🤖 ATR Bot initialized: {self.symbol} {self.timeframe}")
        logging.info(f"💰 Account Size: ${self.account_size:.2f}")
        logging.info(f"📊 EMA: {self.ema_fast}/{self.ema_slow} | ATR: {self.sl_atr_multiplier}x")
        logging.info(f"🔶 Mode: {'TESTNET' if self.is_testnet else 'MAINNET'}")

    def _init_exchange(self, config):
        """Binance ulanishini sozlash"""
        try:
            exchange = ccxt.binance({
                'apiKey': config.get('api_key', ''),
                'secret': config.get('api_secret', ''),
                'enableRateLimit': True,
                'timeout': 30000
            })

            if self.is_testnet:
                exchange.set_sandbox_mode(True)
                logging.info("🔶 TESTNET MODE ENABLED")

            balance = exchange.fetch_balance()
            logging.info(f"✅ Binance connected")
            return exchange
        except Exception as e:
            logging.error(f"❌ Exchange init error: {e}")
            raise

    def get_candles(self, limit=100):
        """OHLCV ma'lumotlarini olish"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            logging.error(f"Candle fetch error: {e}")
            return None

    def calculate_indicators(self, df):
        """Indikatorlarni hisoblash: EMA, ATR, RSI"""
        df['ema_20'] = df['close'].ewm(span=self.ema_fast).mean()
        df['ema_50'] = df['close'].ewm(span=self.ema_slow).mean()

        # ATR (Average True Range) - ETH'da muhim!
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift()),
                abs(df['low'] - df['close'].shift())
            )
        )
        df['atr'] = df['tr'].rolling(window=self.atr_period).mean()

        # RSI filter
        df['rsi'] = self._calculate_rsi(df['close'], self.rsi_period)
        return df

    def _calculate_rsi(self, prices, period=14):
        """RSI hisoblash"""
        deltas = np.diff(prices)
        seed = deltas[:period + 1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period

        rs = up / down if down != 0 else 0
        rsi = np.zeros_like(prices)
        rsi[:period] = 100. - 100. / (1. + rs)

        for i in range(period, len(prices)):
            delta = deltas[i - 1]
            upval = delta if delta > 0 else 0
            downval = -delta if delta < 0 else 0

            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period
            rs = up / down if down != 0 else 0
            rsi[i] = 100. - 100. / (1. + rs)

        return rsi

    def has_lower_wick_buy(self, candle):
        """BUY: pastki soya + yopilish EMA 20 ustida"""
        if candle['low'] == candle['open']:
            return False
        wick_ratio = (candle['open'] - candle['low']) / (candle['high'] - candle['low'])
        return wick_ratio > 0.25  # ETH uchun biroz relaksli

    def has_upper_wick_sell(self, candle):
        """SELL: yuqori soya + yopilish EMA 20 ostida"""
        if candle['high'] == candle['open']:
            return False
        wick_ratio = (candle['high'] - candle['open']) / (candle['high'] - candle['low'])
        return wick_ratio > 0.25

    def check_buy_signal(self, df):
        """BUY signalni tekshirish (ETHUSDT)"""
        if len(df) < max(self.ema_slow, self.atr_period):
            return False

        current = df.iloc[-1]

        # 1. TREND: EMA 20 > EMA 50 (MAJBURIY)
        if current['ema_20'] <= current['ema_50']:
            return False

        # 2. PULLBACK: Narx EMA 20 da pastda
        if current['close'] >= current['ema_20']:
            return False

        # 3. CANDLE: Pastki soya + yopilish EMA 20 ustida
        if not self.has_lower_wick_buy(current):
            return False
        if current['close'] <= current['ema_20']:
            return False

        # 4. RSI FILTER: 45-65 (ETH uchun)
        if current['rsi'] < self.rsi_filter_min or current['rsi'] > self.rsi_filter_max:
            return False

        # 5. ATR mavjud
        if pd.isna(current['atr']) or current['atr'] == 0:
            return False

        # 6. SESSION FILTER
        if not self.is_trading_session():
            return False

        # 7. Daily trade limit
        if self.daily_trades_count >= self.max_trades_per_day:
            return False

        logging.info(f"✅ BUY SIGNAL | Price: ${current['close']:.2f} | RSI: {current['rsi']:.1f}")
        return True

    def check_sell_signal(self, df):
        """SELL signalni tekshirish (ETHUSDT)"""
        if len(df) < max(self.ema_slow, self.atr_period):
            return False

        current = df.iloc[-1]

        # 1. TREND: EMA 20 < EMA 50 (MAJBURIY)
        if current['ema_20'] >= current['ema_50']:
            return False

        # 2. PULLBACK: Narx EMA 20 da yuqorida
        if current['close'] <= current['ema_20']:
            return False

        # 3. CANDLE: Yuqori soya + yopilish EMA 20 ostida
        if not self.has_upper_wick_sell(current):
            return False
        if current['close'] >= current['ema_20']:
            return False

        # 4. RSI FILTER: 35-55 (SELL uchun alib past)
        if current['rsi'] < (self.rsi_filter_min - 10) or current['rsi'] > (self.rsi_filter_max - 10):
            return False

        # 5. ATR mavjud
        if pd.isna(current['atr']) or current['atr'] == 0:
            return False

        # 6. SESSION FILTER
        if not self.is_trading_session():
            return False

        # 7. Daily trade limit
        if self.daily_trades_count >= self.max_trades_per_day:
            return False

        logging.info(f"✅ SELL SIGNAL | Price: ${current['close']:.2f} | RSI: {current['rsi']:.1f}")
        return True

    def is_trading_session(self):
        """Trading vaqti (24/7 uchun crypto, lekin hammasini qabul qil)"""
        if not self.use_session_filter:
            return True

        now = datetime.utcnow()
        hour = now.hour
        day = now.weekday()

        # Juma-Shanba: yimlik (lekin H1 da oz risk bo'lsa ok)
        if day >= 4:
            # Juma: Limited trading
            if self.timeframe in ['30m', '1h']:
                return 8 <= hour < 20  # Kamroq vaqt
            return False

        # Dushanba-Payshanba: normal
        return True

    def calculate_position_size(self, atr, entry_price, signal_type):
        """Position size: Risk per trade (1% risk = SL distance)"""
        sl_distance = atr * self.sl_atr_multiplier
        risk_amount = (self.account_size * self.risk_per_trade) / 100

        # lot_size = risk_amount / sl_distance
        lot_size = risk_amount / sl_distance

        return max(0.001, lot_size)  # Min 0.001 ETH

    def execute_buy(self, entry_price, atr, current_rsi):
        """BUY orderni bajarish"""
        try:
            sl = entry_price - (atr * self.sl_atr_multiplier)
            tp = entry_price + (atr * self.sl_atr_multiplier * self.rr_ratio)

            lot_size = self.calculate_position_size(atr, entry_price, "BUY")

            position = {
                'entry_time': datetime.now().isoformat(),
                'type': 'BUY',
                'entry_price': entry_price,
                'size': lot_size,
                'stop_loss': sl,
                'take_profit': tp,
                'atr': atr,
                'rsi': current_rsi,
                'sl_distance': atr * self.sl_atr_multiplier,
                'tp_distance': atr * self.sl_atr_multiplier * self.rr_ratio,
                'status': 'OPEN'
            }

            self.open_positions.append(position)
            self.daily_trades_count += 1
            self.last_trade_time = datetime.now()

            msg = f"""
🟢 BUY SIGNAL EXECUTED

Asset: {self.symbol}
Entry: ${entry_price:.2f}
Stop Loss: ${sl:.2f}
Take Profit: ${tp:.2f}
Size: {lot_size:.4f}
Risk:Reward: 1:{self.rr_ratio}
RSI: {current_rsi:.1f}
"""
            self.send_telegram(msg)
            logging.info(f"✅ BUY executed @ ${entry_price:.2f}")

            return position
        except Exception as e:
            logging.error(f"BUY execute error: {e}")
            return None

    def execute_sell(self, entry_price, atr, current_rsi):
        """SELL orderni bajarish"""
        try:
            sl = entry_price + (atr * self.sl_atr_multiplier)
            tp = entry_price - (atr * self.sl_atr_multiplier * self.rr_ratio)

            lot_size = self.calculate_position_size(atr, entry_price, "SELL")

            position = {
                'entry_time': datetime.now().isoformat(),
                'type': 'SELL',
                'entry_price': entry_price,
                'size': lot_size,
                'stop_loss': sl,
                'take_profit': tp,
                'atr': atr,
                'rsi': current_rsi,
                'sl_distance': atr * self.sl_atr_multiplier,
                'tp_distance': atr * self.sl_atr_multiplier * self.rr_ratio,
                'status': 'OPEN'
            }

            self.open_positions.append(position)
            self.daily_trades_count += 1
            self.last_trade_time = datetime.now()

            msg = f"""
🔴 SELL SIGNAL EXECUTED

Asset: {self.symbol}
Entry: ${entry_price:.2f}
Stop Loss: ${sl:.2f}
Take Profit: ${tp:.2f}
Size: {lot_size:.4f}
Risk:Reward: 1:{self.rr_ratio}
RSI: {current_rsi:.1f}
"""
            self.send_telegram(msg)
            logging.info(f"✅ SELL executed @ ${entry_price:.2f}")

            return position
        except Exception as e:
            logging.error(f"SELL execute error: {e}")
            return None

    def check_exit_conditions(self, current_price):
        """Exit: SL/TP tekshirish"""
        for i, position in enumerate(self.open_positions):
            should_exit = False
            exit_reason = ""

            if position['type'] == 'BUY':
                if current_price <= position['stop_loss']:
                    should_exit = True
                    exit_reason = "STOP_LOSS"
                elif current_price >= position['take_profit']:
                    should_exit = True
                    exit_reason = "TAKE_PROFIT"

            elif position['type'] == 'SELL':
                if current_price >= position['stop_loss']:
                    should_exit = True
                    exit_reason = "STOP_LOSS"
                elif current_price <= position['take_profit']:
                    should_exit = True
                    exit_reason = "TAKE_PROFIT"

            if should_exit:
                self.close_position(i, current_price, exit_reason)
                break

    def close_position(self, index, exit_price, reason):
        """Pozitsiyani yopish"""
        position = self.open_positions[index]

        if position['type'] == 'BUY':
            pnl = (exit_price - position['entry_price']) * position['size']
        else:
            pnl = (position['entry_price'] - exit_price) * position['size']

        pnl_pct = (pnl / (position['entry_price'] * position['size'])) * 100 if position['entry_price'] > 0 else 0

        position['exit_price'] = exit_price
        position['exit_time'] = datetime.now().isoformat()
        position['pnl'] = pnl
        position['pnl_pct'] = pnl_pct
        position['reason'] = reason
        position['status'] = 'WIN' if pnl > 0 else 'LOSS'

        if pnl < 0:
            self.daily_loss += pnl

        self.trades_history.append(position)

        msg = f"""
❌ POSITION CLOSED

Type: {position['type']}
Entry: ${position['entry_price']:.2f}
Exit: ${exit_price:.2f}
P/L: ${pnl:.2f} ({pnl_pct:+.2f}%)
Reason: {reason}
"""
        self.send_telegram(msg)
        logging.info(f"❌ Position closed: {reason} | P/L: ${pnl:.2f}")

        self.open_positions.pop(index)

    def send_telegram(self, message):
        """Telegram xabar"""
        if not self.telegram_token or not self.telegram_chat_id:
            return

        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {'chat_id': self.telegram_chat_id, 'text': message, 'parse_mode': 'HTML'}
            requests.post(url, data=data, timeout=5)
        except Exception as e:
            logging.error(f"Telegram error: {e}")

    def reset_daily_stats(self):
        """Kunlik reset"""
        now = datetime.now()
        if not hasattr(self, '_daily_reset_date') or self._daily_reset_date != now.date():
            self.daily_loss = 0
            self.daily_trades_count = 0
            self.daily_start_balance = self.account_size
            self._daily_reset_date = now.date()
            logging.info("🔄 Daily stats reset")

    def run(self):
        """Bot loop"""
        self.is_running = True

        self.send_telegram(f"""
✅ ATR TREND PULLBACK BOT STARTED

🔮 Mode: {'TESTNET' if self.is_testnet else 'MAINNET'}
📊 Asset: {self.symbol}
⏰ Timeframe: {self.timeframe}
💰 Account: ${self.account_size:.2f}
📈 Strategy: ETH Optimized
""")

        logging.info("🚀 Bot started")

        while self.is_running:
            try:
                self.reset_daily_stats()

                df = self.get_candles(100)
                if df is None or len(df) < self.ema_slow:
                    time.sleep(30)
                    continue

                df = self.calculate_indicators(df)
                current_price = df.iloc[-1]['close']
                current_rsi = df.iloc[-1]['rsi']
                current_atr = df.iloc[-1]['atr']

                if self.open_positions:
                    self.check_exit_conditions(current_price)

                if len(self.open_positions) == 0 and self.daily_trades_count < self.max_trades_per_day:
                    if self.check_buy_signal(df):
                        self.execute_buy(current_price, current_atr, current_rsi)
                    elif self.check_sell_signal(df):
                        self.execute_sell(current_price, current_atr, current_rsi)

                # Sleep based on timeframe
                sleep_times = {'30m': 1700, '1h': 3600, '2h': 7200, '4h': 14400}
                sleep_time = sleep_times.get(self.timeframe, 1800)
                time.sleep(sleep_time)

            except Exception as e:
                logging.error(f"Loop error: {e}")
                time.sleep(60)

        self.send_telegram("🛑 BOT STOPPED")

    def stop(self):
        """Stop bot"""
        self.is_running = False
        logging.info("🛑 Bot stopping...")