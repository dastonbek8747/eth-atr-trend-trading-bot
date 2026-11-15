# 💰 ETHUSDT ATR Trend Pullback Bot

Binance (spot/testnet) uchun **ATR Trend Pullback** strategiyasiga asoslangan avtomatik savdo boti. Streamlit veb-interfeys orqali boshqariladi.

> ⚠️ **Diqqat:** bu bot haqiqiy pul bilan savdo qilishi mumkin. Avval **testnet**da sinab ko'ring.

---

## ✨ Imkoniyatlar

- 📈 **Strategiya:** EMA(20/50) trend + ATR pullback + sham soyasi (wick) + RSI filtri
- 🎯 **Risk boshqaruvi:** har savdoga risk foizi, SL/TP (ATR asosida), kunlik savdo limiti, kunlik zarar limiti
- 🕐 **Sessiya filtri:** dam olish kunlari savdoni cheklash
- 📊 **Streamlit panel:** real vaqt balans, ochiq pozitsiyalar, savdo tarixi, grafiklar
- 🔔 **Telegram xabarnomalar:** signal, pozitsiya ochilishi/yopilishi
- 🧪 **Testnet rejimi:** xavfsiz sinov

---

## 🛠 Texnologiyalar

| Texnologiya | Maqsad |
|---|---|
| **Python 3.10+** | Asosiy til |
| **ccxt** | Binance birjasi bilan aloqa |
| **pandas / numpy** | Indikatorlar hisobi |
| **Streamlit** | Veb-interfeys |
| **Plotly** | Grafiklar |
| **python-dotenv** | Muhit o'zgaruvchilari |

---

## ⚙️ O'rnatish

```bash
git clone https://github.com/dastonbek8747/sssssss.git
cd ssssss
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

`.env.example` dan nusxa oling va kalitlaringizni kiriting:

```bash
cp .env.example .env
```

```env
BINANCE_API_KEY=...
BINANCE_API_SECRET=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

> 🔒 `.env` fayli **hech qachon** git'ga qo'shilmasin (`.gitignore`da mavjud).

---

## ▶️ Ishga tushirish

```bash
streamlit run main.py
```

Brauzerda `http://localhost:8501` ochiladi. Sidebar'dan sozlamalarni kiritib, botni ishga tushiring.

---

## 📁 Loyiha tuzilishi

```
sssssss/
├── main.py           # Streamlit interfeys
├── avto_savdo.py     # Savdo boti mantiqi (ATRTrendPullbackBot)
├── requirements.txt
├── tests/            # Signal mantiqi testlari
└── .env.example
```

---

## 🧪 Testlar

```bash
python -m unittest discover tests -v
```

---

## ⚠️ Ogohlantirish

Bu loyiha **ta'lim maqsadida** yaratilgan. Savdo botlarini haqiqiy bozorda ishlatish **moliyaviy zarar** keltirishi mumkin. Muallif yuzaga keladigan zarar uchun javobgar emas.

---

## 📄 Litsenziya

Litsenziya ko'rsatilmagan.
