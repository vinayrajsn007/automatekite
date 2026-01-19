"""
Fetch NIFTY Options Historical Data using Kite API
Uses direct API call with proper authentication
"""

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv('KITE_API_KEY')
ACCESS_TOKEN = os.getenv('KITE_ACCESS_TOKEN')

# NIFTY Options for 20th Jan 2026, Strike 25500-26000
OPTIONS = {
    # CE Options
    'NIFTY2612025500CE': 12185346,
    'NIFTY2612025550CE': 12185858,
    'NIFTY2612025600CE': 12186370,
    'NIFTY2612025650CE': 12188418,
    'NIFTY2612025700CE': 12188930,
    'NIFTY2612025750CE': 12189442,
    'NIFTY2612025800CE': 12189954,
    'NIFTY2612025850CE': 12190466,
    'NIFTY2612025900CE': 12190978,
    'NIFTY2612025950CE': 12191490,
    'NIFTY2612026000CE': 12192002,
    # PE Options
    'NIFTY2612025500PE': 12185602,
    'NIFTY2612025550PE': 12186114,
    'NIFTY2612025600PE': 12186626,
    'NIFTY2612025650PE': 12188674,
    'NIFTY2612025700PE': 12189186,
    'NIFTY2612025750PE': 12189698,
    'NIFTY2612025800PE': 12190210,
    'NIFTY2612025850PE': 12190722,
    'NIFTY2612025900PE': 12191234,
    'NIFTY2612025950PE': 12191746,
    'NIFTY2612026000PE': 12192258,
}


def fetch_historical_data(instrument_token, symbol, from_date, to_date, interval="day"):
    """
    Fetch historical data using direct API call
    """
    url = f"https://api.kite.trade/instruments/historical/{instrument_token}/{interval}"
    
    params = {
        'from': from_date,
        'to': to_date,
        'oi': 1  # Include Open Interest
    }
    
    headers = {
        'X-Kite-Version': '3',
        'Authorization': f'token {API_KEY}:{ACCESS_TOKEN}'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('data', {}).get('candles', [])
        else:
            print(f"Error for {symbol}: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Exception for {symbol}: {e}")
        return None


def main():
    print("""
╔═══════════════════════════════════════════════════════════════════════════════════╗
║     NIFTY OPTIONS HISTORICAL DATA - 16th January 2026                             ║
║     Strike Range: 25500 - 26000 | CE and PE                                       ║
╚═══════════════════════════════════════════════════════════════════════════════════╝
    """)
    
    if not API_KEY or not ACCESS_TOKEN:
        print("❌ API_KEY or ACCESS_TOKEN not found in .env file")
        return
    
    print(f"API Key: {API_KEY[:8]}...")
    print(f"Access Token: {ACCESS_TOKEN[:8]}...")
    
    # Date range - 16th January 2026
    from_date = "2026-01-16 09:15:00"
    to_date = "2026-01-16 15:30:00"
    
    print(f"\n📅 Fetching data for: {from_date[:10]}")
    print("-" * 80)
    
    results = {}
    
    for symbol, token in OPTIONS.items():
        print(f"Fetching {symbol}...", end=" ")
        
        candles = fetch_historical_data(token, symbol, from_date, to_date, "day")
        
        if candles and len(candles) > 0:
            # Candle format: [timestamp, open, high, low, close, volume, oi]
            candle = candles[-1]
            results[symbol] = {
                'open': candle[1],
                'high': candle[2],
                'low': candle[3],
                'close': candle[4],
                'volume': candle[5],
                'oi': candle[6] if len(candle) > 6 else 0
            }
            print(f"✓ Close: ₹{candle[4]:.2f}")
        else:
            print("✗ No data")
    
    # Display results in option chain format
    if results:
        print("\n" + "=" * 140)
        print(f"  NIFTY OPTION CHAIN - 16th January 2026 (Historical)")
        print("=" * 140)
        print(f"{'CE Symbol':<22} {'CE Open':<10} {'CE High':<10} {'CE Low':<10} {'CE Close':<10} {'Strike':<8} {'PE Close':<10} {'PE Low':<10} {'PE High':<10} {'PE Open':<10} {'PE Symbol':<22}")
        print("-" * 140)
        
        strikes = [25500, 25550, 25600, 25650, 25700, 25750, 25800, 25850, 25900, 25950, 26000]
        
        for strike in strikes:
            ce_symbol = f"NIFTY26120{strike}CE"
            pe_symbol = f"NIFTY26120{strike}PE"
            
            ce = results.get(ce_symbol, {})
            pe = results.get(pe_symbol, {})
            
            ce_open = f"₹{ce.get('open', 0):.2f}" if ce.get('open') else "-"
            ce_high = f"₹{ce.get('high', 0):.2f}" if ce.get('high') else "-"
            ce_low = f"₹{ce.get('low', 0):.2f}" if ce.get('low') else "-"
            ce_close = f"₹{ce.get('close', 0):.2f}" if ce.get('close') else "-"
            
            pe_open = f"₹{pe.get('open', 0):.2f}" if pe.get('open') else "-"
            pe_high = f"₹{pe.get('high', 0):.2f}" if pe.get('high') else "-"
            pe_low = f"₹{pe.get('low', 0):.2f}" if pe.get('low') else "-"
            pe_close = f"₹{pe.get('close', 0):.2f}" if pe.get('close') else "-"
            
            print(f"{ce_symbol:<22} {ce_open:<10} {ce_high:<10} {ce_low:<10} {ce_close:<10} {strike:<8} {pe_close:<10} {pe_low:<10} {pe_high:<10} {pe_open:<10} {pe_symbol:<22}")
        
        print("=" * 140)
        print(f"\n✅ Successfully fetched {len(results)} option prices")
    else:
        print("\n⚠️  No historical data retrieved. Check API permissions.")


if __name__ == "__main__":
    main()
