import streamlit as st
import json
import time
from datetime import datetime, timedelta
from avto_savdo import ATRTrendPullbackBot
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import threading
import os
from dotenv import load_dotenv
import pickle

load_dotenv()

st.set_page_config(
    page_title="ETHUSDT ATR Bot",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# MODERN DARK DESIGN
st.markdown("""
<style>
    [data-testid="stMainBlockContainer"] {
        background: linear-gradient(135deg, #0a0e27 0%, #1a1a3e 100%);
        padding: 2rem;
    }
    .main-title {
        background: linear-gradient(135deg, #ffd700 0%, #ffed4e 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
    }
    .balance-box {
        background: linear-gradient(135deg, #00d084 0%, #00a86b 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        box-shadow: 0 8px 32px rgba(0, 208, 132, 0.3);
        font-size: 1.3rem;
        font-weight: bold;
    }
    .profit-box {
        background: linear-gradient(135deg, #ffd700 0%, #ffed4e 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: black;
        text-align: center;
        box-shadow: 0 8px 32px rgba(255, 215, 0, 0.3);
        font-size: 1.2rem;
        font-weight: bold;
    }
    .loss-box {
        background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        box-shadow: 0 8px 32px rgba(255, 107, 107, 0.3);
    }
    .status-active {
        background: linear-gradient(135deg, #00d4ff 0%, #0099ff 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        animation: pulse 2s infinite;
        box-shadow: 0 8px 32px rgba(0, 212, 255, 0.3);
    }
    .status-stopped {
        background: #666;
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
</style>
""", unsafe_allow_html=True)

# ==================== SESSION STATE (PERSISTENT) ====================
if 'bot_running' not in st.session_state:
    st.session_state.bot_running = False
if 'bot' not in st.session_state:
    st.session_state.bot = None
if 'start_time' not in st.session_state:
    st.session_state.start_time = None
if 'bot_config' not in st.session_state:
    st.session_state.bot_config = {}

# ==================== SIDEBAR ====================
st.sidebar.title("⚙️ Bot Settings")

col_mode1, col_mode2 = st.sidebar.columns(2)
with col_mode1:
    mode = st.selectbox("Mode", ["🔶 TESTNET", "🟢 MAINNET"], index=0)
    is_testnet = "TESTNET" in mode

with col_mode2:
    st.metric("Status", "🟢 RUNNING" if st.session_state.bot_running else "⚪ STOPPED")

st.sidebar.markdown("---")

api_key = os.getenv('BINANCE_API_KEY', '')
api_secret = os.getenv('BINANCE_API_SECRET', '')
telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
chat_id = os.getenv('TELEGRAM_CHAT_ID', '')

if api_key and api_secret:
    st.sidebar.success("✅ API Connected")
else:
    st.sidebar.error("❌ .env missing")

st.sidebar.markdown("---")
st.sidebar.markdown("### 💱 Trading Settings")

symbol = "ETHUSDT"
st.sidebar.info(f"📊 Asset: {symbol}\n✅ Binance")

timeframe = st.sidebar.selectbox(
    "Timeframe",
    ["1m", "5m", "15m", "30m", "1h", "2h", "4h"],
    index=4,
    help="1m=scalp, H1+=swing"
)

account_size = st.sidebar.number_input(
    "Account ($)",
    100.0,
    1000000.0,
    1000.0,
    100.0,
    help="Total balance"
)

max_trades = st.sidebar.slider(
    "Max Trades/Day",
    1, 20, 2, 1,
    help="1-20 trades"
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 EMA Settings")

ema_fast = st.sidebar.slider("EMA Fast", 5, 30, 20, 1)
ema_slow = st.sidebar.slider("EMA Slow", 30, 200, 50, 1)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🎯 ATR & Risk")

atr_period = st.sidebar.slider("ATR Period", 5, 30, 14, 1)
sl_multiplier = st.sidebar.slider("SL ATR ×", 1.0, 5.0, 2.0, 0.1)
rr_ratio = st.sidebar.slider("Risk:Reward", 0.5, 5.0, 2.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔥 RSI & Risk%")

use_rsi = st.sidebar.checkbox("RSI Filter", True)
if use_rsi:
    rsi_min = st.sidebar.slider("RSI Min", 20, 50, 40, 5)
    rsi_max = st.sidebar.slider("RSI Max", 50, 80, 60, 5)
else:
    rsi_min, rsi_max = 0, 100

risk_per_trade = st.sidebar.slider(
    "Risk/Trade (%)",
    0.1, 5.0, 1.0, 0.1,
    help="0.5-1% safe"
)

max_daily_loss = st.sidebar.slider(
    "Max Daily Loss (%)",
    0.5, 20.0, 3.0, 0.5,
    help="3-5% safe"
)

use_session_filter = st.sidebar.checkbox("Session Filter", True)

# ==================== HEADER ====================
st.markdown('<h1 class="main-title">💰 ETHUSDT ATR BOT</h1>', unsafe_allow_html=True)

# ==================== BALANCE DISPLAY ====================
col_balance, col_profit, col_loss, col_time = st.columns(4)

if st.session_state.bot and st.session_state.bot_running:
    current_balance = st.session_state.bot.account_size
    trades = st.session_state.bot.trades_history if hasattr(st.session_state.bot, 'trades_history') else []

    total_profit = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0) if trades else 0
    total_loss = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0) if trades else 0

    with col_balance:
        st.markdown(f'<div class="balance-box">💰 BALANCE<br/>${current_balance:.2f}</div>', unsafe_allow_html=True)

    with col_profit:
        profit_text = f"+${total_profit:.2f}" if total_profit > 0 else "$0.00"
        st.markdown(f'<div class="profit-box">📈 WINS<br/>{profit_text}</div>', unsafe_allow_html=True)

    with col_loss:
        loss_text = f"${total_loss:.2f}" if total_loss < 0 else "$0.00"
        st.markdown(f'<div class="loss-box">📉 LOSSES<br/>{loss_text}</div>', unsafe_allow_html=True)

    with col_time:
        if st.session_state.start_time:
            diff = time.time() - st.session_state.start_time
            hours = int(diff // 3600)
            minutes = int((diff % 3600) // 60)
            elapsed = f"{hours}h {minutes}m"
        else:
            elapsed = "0h 0m"
        st.markdown(f'<div class="status-active">🟢 RUNNING<br/>{elapsed}</div>', unsafe_allow_html=True)
else:
    with col_balance:
        st.markdown('<div class="balance-box">💰 BALANCE<br/>$0.00</div>', unsafe_allow_html=True)
    with col_profit:
        st.markdown('<div class="profit-box">📈 WINS<br/>$0.00</div>', unsafe_allow_html=True)
    with col_loss:
        st.markdown('<div class="loss-box">📉 LOSSES<br/>$0.00</div>', unsafe_allow_html=True)
    with col_time:
        st.markdown('<div class="status-stopped">⚪ STOPPED</div>', unsafe_allow_html=True)

st.markdown("---")

# ==================== METRICS ====================
col1, col2, col3, col4, col5 = st.columns(5)

if st.session_state.bot and st.session_state.bot_running:
    trades = st.session_state.bot.trades_history
    total_trades = len(trades)
    open_pos = len(st.session_state.bot.open_positions)
    daily_trades = st.session_state.bot.daily_trades_count

    with col1:
        st.metric("📊 Total Trades", total_trades)
    with col2:
        st.metric("📍 Open", open_pos)
    with col3:
        st.metric("📈 Today", f"{daily_trades}/{max_trades}")
    with col4:
        if total_trades > 0:
            wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
            wr = (wins / total_trades) * 100
        else:
            wr = 0
        st.metric("✅ Win Rate", f"{wr:.1f}%")
    with col5:
        total_pnl = sum(t.get('pnl', 0) for t in trades) if trades else 0
        st.metric("💵 Total P/L", f"${total_pnl:.2f}")
else:
    with col1:
        st.metric("📊 Total Trades", "0")
    with col2:
        st.metric("📍 Open", "0")
    with col3:
        st.metric("📈 Today", "0/20")
    with col4:
        st.metric("✅ Win Rate", "0%")
    with col5:
        st.metric("💵 Total P/L", "$0.00")

st.markdown("---")

# ==================== BUTTONS ====================
col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)


def run_bot():
    if not api_key or not api_secret:
        st.error("❌ API keys required!")
        return

    config = {
        'symbol': symbol, 'timeframe': timeframe, 'account_size': account_size,
        'is_testnet': is_testnet, 'ema_fast': ema_fast, 'ema_slow': ema_slow,
        'atr_period': atr_period, 'sl_atr_multiplier': sl_multiplier, 'rr_ratio': rr_ratio,
        'risk_per_trade': risk_per_trade, 'max_daily_loss_pct': max_daily_loss,
        'max_trades_per_day': max_trades, 'use_session_filter': use_session_filter,
        'rsi_period': 14, 'rsi_filter_min': rsi_min, 'rsi_filter_max': rsi_max,
        'api_key': api_key, 'api_secret': api_secret,
        'telegram_token': telegram_token, 'telegram_chat_id': chat_id
    }

    st.session_state.bot_config = config
    bot = ATRTrendPullbackBot(config)
    st.session_state.bot = bot
    st.session_state.bot_running = True
    st.session_state.start_time = time.time()

    bot_thread = threading.Thread(target=bot.run, daemon=True)
    bot_thread.start()

    st.success("✅ Bot Started!")
    st.balloons()
    time.sleep(2)
    st.rerun()


with col_btn1:
    if st.button("🚀 START", use_container_width=True, disabled=st.session_state.bot_running, key="start"):
        run_bot()

with col_btn2:
    if st.button("⏹️ STOP", use_container_width=True, disabled=not st.session_state.bot_running, key="stop"):
        if st.session_state.bot:
            st.session_state.bot.stop()
            time.sleep(1)
        st.session_state.bot_running = False
        st.warning("⏹️ Bot Stopped")
        time.sleep(1)
        st.rerun()

with col_btn3:
    if st.button("🔄 REFRESH", use_container_width=True, key="refresh"):
        st.rerun()

with col_btn4:
    if st.button("📊 STATS", use_container_width=True, key="stats"):
        if st.session_state.bot:
            trades = st.session_state.bot.trades_history
            if trades:
                st.info(
                    f"✅ {len([t for t in trades if t.get('pnl', 0) > 0])} Wins | ❌ {len([t for t in trades if t.get('pnl', 0) <= 0])} Losses")

st.markdown("---")

# ==================== TABS ====================
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Analysis", "📝 History", "📈 Stats", "📋 Positions", "ℹ️ Info"])

with tab1:
    st.subheader("📊 Market Analysis")
    if st.session_state.bot and st.session_state.bot_running:
        try:
            df = st.session_state.bot.get_candles(100)
            if df is not None and len(df) > 0:
                df = st.session_state.bot.calculate_indicators(df)

                fig = make_subplots(rows=4, cols=1, shared_xaxes=True,
                                    vertical_spacing=0.06, row_heights=[0.5, 0.2, 0.15, 0.15],
                                    subplot_titles=('Price & EMA', 'Volume', 'ATR', 'RSI'))

                fig.add_trace(go.Candlestick(x=df['timestamp'], open=df['open'],
                                             high=df['high'], low=df['low'], close=df['close'],
                                             name='Price'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ema_20'],
                                         name=f'EMA {ema_fast}', line=dict(color='orange', width=2)), row=1, col=1)
                fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ema_50'],
                                         name=f'EMA {ema_slow}', line=dict(color='blue', width=2)), row=1, col=1)
                fig.add_trace(go.Bar(x=df['timestamp'], y=df['volume'], name='Volume',
                                     marker_color='rgba(100,100,200,0.3)'), row=2, col=1)
                fig.add_trace(go.Scatter(x=df['timestamp'], y=df['atr'],
                                         name='ATR', line=dict(color='red', width=2)), row=3, col=1)
                fig.add_trace(go.Scatter(x=df['timestamp'], y=df['rsi'],
                                         name='RSI', line=dict(color='purple', width=2)), row=4, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=4, opacity=0.5)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=4, opacity=0.5)

                fig.update_layout(height=800, template='plotly_dark', xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)

                current = df.iloc[-1]
                c1, c2, c3, c4, c5, c6 = st.columns(6)
                with c1:
                    st.metric("💰 Price", f"${current['close']:.2f}")
                with c2:
                    st.metric("📊 ATR", f"{current['atr']:.4f}")
                with c3:
                    st.metric("📈 RSI", f"{current['rsi']:.1f}")
                with c4:
                    trend = "🟢 UP" if current['ema_20'] > current['ema_50'] else "🔴 DOWN"
                    st.metric("Trend", trend)
                with c5:
                    st.metric("Pullback", "📉" if current['close'] < current['ema_20'] else "📈")
                with c6:
                    vol = current['volume'] / (df['volume'].tail(20).mean() + 0.001)
                    st.metric("Vol", f"{vol:.2f}x")
        except Exception as e:
            st.error(f"Error: {e}")
    else:
        st.info("Start bot to see analysis")

with tab2:
    st.subheader("📝 Trade History")
    if st.session_state.bot and hasattr(st.session_state.bot, 'trades_history'):
        trades = st.session_state.bot.trades_history
        if trades:
            df_trades = pd.DataFrame(trades)
            cols = ['entry_time', 'type', 'entry_price', 'exit_price', 'pnl', 'pnl_pct', 'reason']
            st.dataframe(df_trades[[c for c in cols if c in df_trades.columns]], use_container_width=True)
            csv = df_trades.to_csv(index=False)
            st.download_button("📥 Download", csv, file_name=f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        else:
            st.info("No trades")

with tab3:
    st.subheader("📈 Statistics")
    if st.session_state.bot and hasattr(st.session_state.bot, 'trades_history'):
        trades = st.session_state.bot.trades_history
        if trades:
            df_trades = pd.DataFrame(trades)
            profits = df_trades['pnl'].tolist()

            c1, c2 = st.columns(2)
            with c1:
                colors = ['#00d084' if p > 0 else '#ff6b6b' for p in profits]
                fig = go.Figure(data=[go.Bar(x=list(range(len(profits))), y=profits, marker_color=colors)])
                fig.update_layout(title="P/L", height=400, template='plotly_dark')
                st.plotly_chart(fig, use_container_width=True)

            with c2:
                wins = sum(1 for p in profits if p > 0)
                losses = len(profits) - wins
                fig = go.Figure(data=[go.Pie(labels=['Wins', 'Losses'], values=[wins, losses],
                                             marker_colors=['#00d084', '#ff6b6b'])])
                fig.update_layout(title="Ratio", height=400, template='plotly_dark')
                st.plotly_chart(fig, use_container_width=True)

            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                st.metric("Total", len(trades))
            with c2:
                st.metric("Wins", wins)
            with c3:
                st.metric("Losses", losses)
            with c4:
                st.metric("WR%", f"{(wins / len(trades) * 100):.1f}%")
            with c5:
                st.metric("P/L", f"${sum(profits):.2f}")

with tab4:
    st.subheader("📋 Open Positions")
    if st.session_state.bot and hasattr(st.session_state.bot, 'open_positions'):
        positions = st.session_state.bot.open_positions
        if positions:
            for i, pos in enumerate(positions):
                st.markdown(f"**{pos['type']} #{i + 1}**")
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("Entry", f"${pos['entry_price']:.2f}")
                with c2:
                    st.metric("SL", f"${pos['stop_loss']:.2f}")
                with c3:
                    st.metric("TP", f"${pos['take_profit']:.2f}")
                with c4:
                    st.metric("Size", f"{pos['size']:.4f}")
                st.divider()
        else:
            st.info("No open positions")

with tab5:
    st.subheader("ℹ️ Strategy Config")
    st.markdown(f"""
    ### 📊 Current Settings
    - **Asset**: {symbol}
    - **Timeframe**: {timeframe}
    - **Account**: ${account_size:.2f}
    - **EMA**: {ema_fast}/{ema_slow}
    - **ATR**: {atr_period} × {sl_multiplier}
    - **R:R**: 1:{rr_ratio}
    - **Risk**: {risk_per_trade}%
    - **Max Daily Loss**: {max_daily_loss}%
    - **Max Trades**: {max_trades}

    ### 🔧 Status
    - **Running**: {'✅ YES' if st.session_state.bot_running else '⚪ NO'}
    - **Mode**: {'🔶 TESTNET' if is_testnet else '🟢 MAINNET'}
    - **Session Filter**: {'✅ ON' if use_session_filter else '❌ OFF'}
    - **RSI Filter**: {'✅ ON' if use_rsi else '❌ OFF'}
    """)

# ==================== AUTO REFRESH ====================
if st.session_state.bot_running:
    time.sleep(5)
    st.rerun()