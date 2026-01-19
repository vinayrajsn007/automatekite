# Quick Start Guide

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Get API Credentials

1. Go to https://kite.trade/apps/
2. Create a new app or use existing one
3. Note down your **API Key** and **API Secret**

## Step 3: Authenticate (First Time Only)

Run the authentication helper:

```bash
python auth_helper.py
```

This will:
- Ask for your API Key and Secret
- Open browser for login
- Generate access token
- Save it to `.env` file

**OR** manually create `.env` file:

```bash
# Create .env file
cat > .env << EOF
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
KITE_ACCESS_TOKEN=your_access_token_here
EOF
```

## Step 4: Test Connection

```bash
python automated_trading.py
```

This will:
- Connect to Kite API
- Show your profile
- Display available margin
- Verify everything works

## Step 5: Run Trading Scripts

### Basic Usage

```python
from kite_client import KiteTradingClient
from automated_trading import AutomatedTrader

# Initialize
kite = KiteTradingClient()
trader = AutomatedTrader(kite)

# Get price
price = trader.get_current_price("NSE", "RELIANCE")
print(f"RELIANCE Price: {price}")

# Place order (uncomment to execute)
# order_id = trader.place_market_order("NSE", "RELIANCE", "BUY", 1, "MIS")
```

### Run Example Strategy

```bash
python example_strategy.py
```

## Common Commands

### Check Orders
```python
from kite_client import KiteTradingClient
kite = KiteTradingClient()
orders = kite.get_orders()
print(orders)
```

### Check Positions
```python
from kite_client import KiteTradingClient
kite = KiteTradingClient()
positions = kite.get_positions()
print(positions)
```

### Square Off All Positions
```python
from kite_client import KiteTradingClient
from automated_trading import AutomatedTrader

kite = KiteTradingClient()
trader = AutomatedTrader(kite)
trader.square_off_all_positions("MIS")
```

## Troubleshooting

### "API Key and API Secret are required"
- Make sure `.env` file exists with correct credentials
- Or pass credentials directly: `KiteTradingClient(api_key="...", api_secret="...")`

### "Invalid API Key"
- Check your API Key is correct
- Make sure app is active on Kite Connect

### "Invalid Access Token"
- Access token may have expired
- Run `python auth_helper.py` again to regenerate

### "Insufficient Margin"
- Check your account balance
- Reduce order quantity
- Use `kite.get_margins()` to check available margin
