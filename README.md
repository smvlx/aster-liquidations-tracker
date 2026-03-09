# Aster Liquidation Tracker

Real-time liquidation alerts for [Aster](https://asterdex.com) perpetual futures, delivered to Telegram.

The tracker connects to Aster's WebSocket stream, filters liquidations by USD size, and sends formatted messages to your Telegram channel.

```
🔴 #ETH Long Liquidation: $314.9k @ $4,319.2
🟢 #BTC Short Liquidation: $1.2M @ $64,647
```

## Features

- **Real-time** — WebSocket stream with sub-second latency
- **Configurable threshold** — only alert on liquidations above a USD amount you choose
- **Auto-reconnect** — exponential backoff, proactive reconnect before server-side 24 h limit
- **Clean formatting** — dynamic price precision, human-readable USD amounts (k / M)
- **Structured logging** — daily rotation with 7-day retention via [loguru](https://github.com/Delgan/loguru)

## Quick start

```bash
git clone https://github.com/smvlx/aster-liquidations-tracker.git
cd aster-liquidations-tracker

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # then fill in your tokens (see below)
python main.py
```

## Setting up the Telegram bot

1. Open Telegram and search for **@BotFather**.
2. Send `/newbot` and follow the prompts — pick a name and a username.
3. BotFather will reply with a **bot token** (e.g. `123456:ABC-DEF…`). Copy it.
4. Create a **channel** (or group) where you want alerts to appear.
5. Add your new bot to the channel **as an admin** with permission to post messages.
6. Get the **channel ID**:
   - The easiest way: forward any message from the channel to [@userinfobot](https://t.me/userinfobot) — it will reply with the chat ID.
   - Channel IDs usually look like `-100xxxxxxxxxx`.
7. Put both values in your `.env` file:

```env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHANNEL_ID=-100xxxxxxxxxx
```

## Configuration

All settings are read from environment variables (or a `.env` file). See [`.env.example`](.env.example) for the full list.

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | **(required)** | Bot token from @BotFather |
| `TELEGRAM_CHANNEL_ID` | **(required)** | Target channel / group ID |
| `MIN_LIQUIDATION_USD` | `50000` | Minimum USD value to trigger an alert |
| `ASTER_WS_URL` | `wss://fstream.asterdex.com/ws/!forceOrder@arr` | WebSocket endpoint |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `RECONNECT_DELAY` | `5` | Initial reconnect wait in seconds |
| `MAX_RECONNECT_ATTEMPTS` | `10` | Attempts per reconnection cycle |
| `WEBSOCKET_PING_INTERVAL` | `20` | Ping frequency in seconds |
| `WEBSOCKET_PING_TIMEOUT` | `15` | Ping timeout in seconds |
| `STATUS_UPDATE_INTERVAL` | `300` | Interval for status log entries (seconds) |
| `MAX_CONNECTION_LIFETIME` | `3600` | Force reconnect after this many seconds |

### Tuning the filter

`MIN_LIQUIDATION_USD` controls the smallest liquidation (in USD notional) that generates an alert.

- **Lower values** (e.g. `1000`) — more alerts, useful for monitoring smaller markets.
- **Higher values** (e.g. `100000`) — only whale liquidations, less noise.

The USD value is calculated as `price * filled_quantity` for each liquidation event.

## How it works

```
Aster WebSocket (!forceOrder@arr)
        │
        ▼
  ┌─────────────┐
  │  Detector    │  parse JSON → compute USD notional
  │  (asyncio)   │  filter by MIN_LIQUIDATION_USD
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  Telegram    │  format message → send to channel
  │  Bot API     │
  └─────────────┘
```

1. **Connect** to Aster's all-market liquidation stream (`!forceOrder@arr`).
2. **Parse** each `forceOrder` event — extract symbol, side, price, quantity.
3. **Filter** — skip anything below the USD threshold.
4. **Format** — build a concise message with direction indicator, symbol hashtag, USD amount, and price.
5. **Send** — post to the configured Telegram channel.

Liquidation direction:
- `SELL` side = a **long** position was liquidated (forced sell) → 🔴
- `BUY` side = a **short** position was liquidated (forced buy) → 🟢

## Project structure

```
├── main.py                          # Entry point
├── src/
│   ├── aster_config.py              # Configuration (env vars)
│   ├── aster_liquidation_detector.py # Core detection & alerting logic
│   └── aster_symbol_manager.py      # Symbol metadata from exchange API
├── requirements.txt
├── .env.example                     # Template for your .env file
└── logs/                            # Auto-created, daily rotation
```

## License

MIT
