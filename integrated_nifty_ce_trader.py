"""
Integrated NIFTY CE Auto Trader
Based on ADR-004: Combines Options Scanner (ADR-003) + Double Confirmation Strategy (ADR-001)

Features:
- Takes expiry date as user input
- Scans NIFTY CE options in premium range ₹80-₹120
- Uses Double Confirmation (5-min + 2-min) for entry signals
- Automatic quantity calculation based on account balance (90% risk factor)
- Continuous trading loop until market close
- Tracks daily P&L across multiple trades

Usage:
    python integrated_nifty_ce_trader.py
    
    # Or programmatically:
    trader = IntegratedNiftyCETrader()
    trader.run(expiry_date="Jan 23")
"""

import os
import time
import math
from datetime import datetime, timedelta
from dotenv import load_dotenv
from kiteconnect import KiteConnect
import pandas as pd
import numpy as np
import logging
import pytz

# Load environment variables
load_dotenv()

# Import local modules
from indicators import calculate_all_indicators
from nifty_options_scanner import parse_expiry_date, NiftyOptionsScanner

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# IST timezone
IST = pytz.timezone('Asia/Kolkata')


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

TRADER_CONFIG = {
    # Options Scanner (ADR-003)
    "strike_min": 25000,
    "strike_max": 26000,
    "strike_multiple": 100,
    "premium_min": 80,
    "premium_max": 120,
    "scanner_refresh_seconds": 5,
    
    # Quantity Calculation
    "risk_factor": 0.90,  # Use 90% of balance
    "lot_size": 75,       # NIFTY lot size
    
    # Market Hours (IST)
    "market_open_hour": 9,
    "market_open_minute": 15,
    "market_close_hour": 15,
    "market_close_minute": 30,
    "stop_new_trades_minutes": 15,  # Stop new trades 15 min before close
    
    # Double Confirmation (ADR-001)
    "primary_timeframe": "5minute",
    "confirm_timeframe": "2minute",
    "primary_check_seconds": 10,
    "confirm_check_seconds": 5,
    
    # Indicator Parameters
    "supertrend_period": 7,
    "supertrend_multiplier": 3,
    "ema_low_period": 8,
    "ema_low_offset": 9,
    "ema_fast": 8,
    "ema_slow": 9,
    "rsi_period": 14,
    "rsi_max": 65,
    "stoch_rsi_threshold": 50,
    "macd_fast": 5,
    "macd_slow": 13,
    "macd_signal": 6,
    
    # Trading
    "exchange": "NFO",
    "product_type": "MIS",  # Intraday
    "order_type": "MARKET",
    
    # NIFTY Index
    "nifty_instrument_token": 256265,  # NIFTY 50 index token
}


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATED NIFTY CE TRADER CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class IntegratedNiftyCETrader:
    """
    Integrated NIFTY CE Auto Trader
    
    Combines:
    - ADR-003: Options Scanner for instrument selection
    - ADR-001: Double Confirmation Strategy for trade timing
    
    Features:
    - Automatic CE option selection based on premium range
    - Double confirmation (5-min + 2-min) for entry
    - Exit on EMA Low falling or strong bearish signal
    - Continuous trading loop until market close
    - Daily P&L tracking
    """
    
    def __init__(self, kite_client=None, config=None):
        """
        Initialize the trader
        
        Args:
            kite_client: KiteConnect instance (optional)
            config: Configuration dictionary (optional)
        """
        # Merge configuration
        self.config = {**TRADER_CONFIG, **(config or {})}
        
        # Initialize Kite client
        if kite_client:
            self.kite = kite_client
        else:
            api_key = os.getenv('KITE_API_KEY')
            access_token = os.getenv('KITE_ACCESS_TOKEN')
            
            if not api_key or not access_token:
                raise ValueError("KITE_API_KEY and KITE_ACCESS_TOKEN are required")
            
            self.kite = KiteConnect(api_key=api_key)
            self.kite.set_access_token(access_token)
        
        # State variables
        self.expiry_date = None
        self.available_balance = 0
        self.trading_capital = 0
        self.selected_option = None
        self.calculated_quantity = 0
        
        # Position tracking
        self.position_open = False
        self.entry_price = 0
        self.entry_time = None
        self.position_quantity = 0
        self.position_symbol = None
        
        # Trade tracking
        self.trade_cycle = 0
        self.daily_trades = []
        self.total_pnl = 0
        
        # Signal tracking
        self.last_5min_check = None
        self.primary_signal = False
        self.confirm_signal = False
        
        # Scanner instance
        self.scanner = None
        
        # Running state
        self.is_running = False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MARKET HOURS METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_current_time_ist(self):
        """Get current time in IST"""
        return datetime.now(IST)
    
    def is_market_open(self):
        """Check if market is currently open (9:15 AM - 3:30 PM IST)"""
        now = self.get_current_time_ist()
        
        market_open = now.replace(
            hour=self.config['market_open_hour'],
            minute=self.config['market_open_minute'],
            second=0,
            microsecond=0
        )
        market_close = now.replace(
            hour=self.config['market_close_hour'],
            minute=self.config['market_close_minute'],
            second=0,
            microsecond=0
        )
        
        return market_open <= now <= market_close
    
    def get_time_to_market_close(self):
        """Get minutes remaining until market close"""
        now = self.get_current_time_ist()
        market_close = now.replace(
            hour=self.config['market_close_hour'],
            minute=self.config['market_close_minute'],
            second=0,
            microsecond=0
        )
        
        if now > market_close:
            return 0
        
        delta = market_close - now
        return int(delta.total_seconds() / 60)
    
    def should_stop_new_trades(self):
        """Check if we should stop initiating new trades (< 15 min to close)"""
        minutes_to_close = self.get_time_to_market_close()
        return minutes_to_close < self.config['stop_new_trades_minutes']
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ACCOUNT BALANCE METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_account_balance(self):
        """Fetch current available balance from Kite"""
        try:
            margins = self.kite.margins(segment="equity")
            self.available_balance = margins['available']['live_balance']
            self.trading_capital = self.available_balance * self.config['risk_factor']
            
            logger.info(f"Account Balance: ₹{self.available_balance:,.2f}")
            logger.info(f"Trading Capital ({self.config['risk_factor']*100:.0f}%): ₹{self.trading_capital:,.2f}")
            
            return self.available_balance
        except Exception as e:
            logger.error(f"Error fetching account balance: {e}")
            raise
    
    def refresh_balance_before_buy(self):
        """Refresh balance immediately before placing a buy order"""
        logger.info("Refreshing balance before buy order...")
        return self.get_account_balance()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # OPTIONS SCANNER METHODS (ADR-003)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def initialize_scanner(self):
        """Initialize the options scanner with current configuration"""
        scanner_config = {
            "strike_min": self.config['strike_min'],
            "strike_max": self.config['strike_max'],
            "strike_multiple": self.config['strike_multiple'],
            "premium_min": self.config['premium_min'],
            "premium_max": self.config['premium_max'],
            "refresh_interval_seconds": self.config['scanner_refresh_seconds'],
            "expiry_date": self.expiry_date,
            "option_types": ["CE"]  # Only CE options
        }
        
        self.scanner = NiftyOptionsScanner(kite_client=self.kite, config=scanner_config)
        self.scanner.load_nifty_options()
        
        logger.info(f"Scanner initialized for expiry: {self.expiry_date}")
    
    def get_nifty_spot_price(self):
        """Get current NIFTY spot price"""
        try:
            quote = self.kite.quote(["NSE:NIFTY 50"])
            return quote.get("NSE:NIFTY 50", {}).get("last_price", 0)
        except Exception as e:
            logger.error(f"Error fetching NIFTY spot: {e}")
            return 0
    
    def select_best_ce_option(self):
        """
        Select the best CE option based on ADR-003 criteria:
        1. Premium in range ₹80-₹120
        2. Closest to ATM
        3. Premium closest to ₹100 (middle of range)
        
        Returns:
            Selected option dictionary or None
        """
        try:
            # Get filtered options from scanner
            result = self.scanner.get_filtered_options()
            ce_options = result.get('ce_options', [])
            nifty_spot = result.get('nifty_spot', 0)
            
            if not ce_options:
                logger.warning("No CE options found in premium range")
                return None
            
            # Calculate ATM strike
            atm_strike = round(nifty_spot / 100) * 100
            
            # Score each option
            # Priority: ATM > nearest OTM > nearest ITM
            # Tiebreaker: premium closest to ₹100
            def score_option(opt):
                strike_diff = abs(opt['strike'] - atm_strike)
                premium_diff = abs(opt['ltp'] - 100)
                # Lower score is better
                return (strike_diff, premium_diff)
            
            # Sort by score
            ce_options_sorted = sorted(ce_options, key=score_option)
            
            selected = ce_options_sorted[0]
            self.selected_option = {
                'tradingsymbol': selected['symbol'],
                'instrument_token': selected['instrument_token'],
                'strike': selected['strike'],
                'expiry': selected['expiry'],
                'ltp': selected['ltp'],
                'lot_size': self.config['lot_size']
            }
            
            logger.info(f"Selected CE Option: {self.selected_option['tradingsymbol']} "
                       f"@ ₹{self.selected_option['ltp']:.2f}")
            
            return self.selected_option
            
        except Exception as e:
            logger.error(f"Error selecting CE option: {e}")
            return None
    
    def refresh_option_premium(self):
        """Refresh the current premium of selected option"""
        if not self.selected_option:
            return None
        
        try:
            symbol = f"{self.config['exchange']}:{self.selected_option['tradingsymbol']}"
            quote = self.kite.quote([symbol])
            
            if symbol in quote:
                self.selected_option['ltp'] = quote[symbol]['last_price']
                return self.selected_option['ltp']
        except Exception as e:
            logger.error(f"Error refreshing premium: {e}")
        
        return None
    
    # ═══════════════════════════════════════════════════════════════════════════
    # QUANTITY CALCULATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def calculate_quantity(self, option_premium=None):
        """
        Calculate trading quantity based on balance and option premium
        
        Formula:
        - Cost per lot = Premium × Lot Size
        - Max lots = floor(Trading Capital / Cost per lot)
        - Quantity = Max lots × Lot Size
        
        Args:
            option_premium: Option premium (uses selected_option if not provided)
        
        Returns:
            Quantity to trade
        """
        if option_premium is None:
            if self.selected_option:
                option_premium = self.selected_option['ltp']
            else:
                return 0
        
        lot_size = self.config['lot_size']
        cost_per_lot = option_premium * lot_size
        
        if cost_per_lot <= 0:
            return 0
        
        max_lots = math.floor(self.trading_capital / cost_per_lot)
        quantity = max_lots * lot_size
        
        self.calculated_quantity = quantity
        
        logger.info(f"Quantity Calculation:")
        logger.info(f"  Cost per Lot: ₹{option_premium:.2f} × {lot_size} = ₹{cost_per_lot:,.2f}")
        logger.info(f"  Max Lots: floor(₹{self.trading_capital:,.2f} / ₹{cost_per_lot:,.2f}) = {max_lots}")
        logger.info(f"  Quantity: {max_lots} × {lot_size} = {quantity}")
        
        return quantity
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DOUBLE CONFIRMATION METHODS (ADR-001)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_historical_data(self, interval, days=5):
        """
        Fetch NIFTY historical data for indicator calculation
        
        Args:
            interval: Candle interval ('5minute', '2minute')
            days: Number of days to fetch
        
        Returns:
            DataFrame with OHLC data
        """
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)
            
            data = self.kite.historical_data(
                instrument_token=self.config['nifty_instrument_token'],
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            
            df = pd.DataFrame(data)
            if not df.empty:
                df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            
            return df
        except Exception as e:
            logger.error(f"Error fetching historical data ({interval}): {e}")
            return pd.DataFrame()
    
    def check_buy_conditions(self, df, timeframe="5minute"):
        """
        Check all buy conditions for a timeframe (ADR-001)
        
        Conditions:
        1. SuperTrend (7,3) Direction = 1 (Bullish)
        2. Close > SuperTrend Value
        3. Close > EMA Low (8, offset 9)
        4. EMA 8 > EMA 9 (Bullish Crossover)
        5. StochRSI < 50 OR Rising
        6. RSI < 65 AND Rising
        7. MACD Histogram > 0 OR Improving
        
        Returns:
            Tuple of (signal_active, details_dict)
        """
        if len(df) < 20:
            return False, {"error": "Insufficient data"}
        
        # Calculate indicators
        df = calculate_all_indicators(df)
        
        current = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3] if len(df) > 2 else prev
        
        conditions = {}
        
        # 1. SuperTrend Bullish
        conditions['supertrend_bullish'] = current['supertrend_direction'] == 1
        
        # 2. Close > SuperTrend
        conditions['close_above_st'] = current['close'] > current['supertrend']
        
        # 3. Close > EMA Low
        conditions['close_above_ema_low'] = current['close'] > current['ema_low_8']
        
        # 4. EMA 8 > EMA 9
        conditions['ema_bullish'] = current['ema_8'] > current['ema_9']
        
        # 5. StochRSI < 50 OR Rising
        stoch_rising = current['stoch_rsi_k'] > prev['stoch_rsi_k']
        conditions['stoch_ok'] = current['stoch_rsi_k'] < self.config['stoch_rsi_threshold'] or stoch_rising
        
        # 6. RSI < 65 AND Rising
        rsi_rising = current['rsi_14'] > prev['rsi_14']
        conditions['rsi_ok'] = current['rsi_14'] < self.config['rsi_max'] and rsi_rising
        
        # 7. MACD Histogram > 0 OR Improving
        macd_improving = current['macd_hist'] > prev['macd_hist']
        conditions['macd_ok'] = current['macd_hist'] > 0 or macd_improving
        
        # All conditions must be true
        all_conditions_met = all(conditions.values())
        
        # Add indicator values for display
        conditions['values'] = {
            'close': current['close'],
            'supertrend': current['supertrend'],
            'supertrend_dir': 'BULLISH' if current['supertrend_direction'] == 1 else 'BEARISH',
            'ema_low': current['ema_low_8'],
            'ema_8': current['ema_8'],
            'ema_9': current['ema_9'],
            'stoch_rsi': current['stoch_rsi_k'],
            'rsi': current['rsi_14'],
            'macd_hist': current['macd_hist']
        }
        
        return all_conditions_met, conditions
    
    def check_exit_conditions(self, df_2min):
        """
        Check exit conditions on 2-minute timeframe (ADR-001)
        
        Exit Trigger 1: EMA Low Falling
        - EMA Low falling for 2+ candles AND price below EMA Low
        
        Exit Trigger 2: Strong Bearish Signal
        - SuperTrend bearish AND EMA 8 < EMA 9 AND Close < EMA Low
        
        Returns:
            Tuple of (should_exit, exit_reason, details)
        """
        if len(df_2min) < 5:
            return False, None, {"error": "Insufficient data"}
        
        # Calculate indicators
        df_2min = calculate_all_indicators(df_2min)
        
        current = df_2min.iloc[-1]
        prev = df_2min.iloc[-2]
        prev2 = df_2min.iloc[-3]
        
        # Exit Trigger 1: EMA Low Falling
        ema_low_falling = (
            current['ema_low_8'] < prev['ema_low_8'] and
            prev['ema_low_8'] < prev2['ema_low_8']
        )
        price_below_ema = current['close'] < current['ema_low_8']
        
        exit_trigger_1 = ema_low_falling and price_below_ema
        
        # Exit Trigger 2: Strong Bearish
        strong_bearish = (
            current['supertrend_direction'] == -1 and  # Bearish SuperTrend
            current['ema_8'] < current['ema_9'] and    # EMA crossed down
            current['close'] < current['ema_low_8']    # Price below EMA Low
        )
        
        exit_trigger_2 = strong_bearish
        
        details = {
            'ema_low_falling': ema_low_falling,
            'price_below_ema': price_below_ema,
            'strong_bearish': strong_bearish,
            'values': {
                'close': current['close'],
                'ema_low': current['ema_low_8'],
                'supertrend_dir': 'BULLISH' if current['supertrend_direction'] == 1 else 'BEARISH',
                'ema_8': current['ema_8'],
                'ema_9': current['ema_9']
            }
        }
        
        if exit_trigger_1:
            return True, "ema_low_falling", details
        elif exit_trigger_2:
            return True, "strong_bearish", details
        
        return False, None, details
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ORDER EXECUTION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def place_buy_order(self, symbol, quantity):
        """
        Place a MARKET BUY order
        
        Args:
            symbol: Trading symbol
            quantity: Order quantity
        
        Returns:
            Order ID or None
        """
        try:
            order_id = self.kite.place_order(
                variety="regular",
                exchange=self.config['exchange'],
                tradingsymbol=symbol,
                transaction_type="BUY",
                quantity=quantity,
                product=self.config['product_type'],
                order_type=self.config['order_type'],
                validity="DAY"
            )
            
            logger.info(f"BUY Order Placed - ID: {order_id}")
            return order_id
            
        except Exception as e:
            logger.error(f"Error placing BUY order: {e}")
            return None
    
    def place_sell_order(self, symbol, quantity, reason="manual"):
        """
        Place a MARKET SELL order
        
        Args:
            symbol: Trading symbol
            quantity: Order quantity
            reason: Exit reason for logging
        
        Returns:
            Order ID or None
        """
        try:
            order_id = self.kite.place_order(
                variety="regular",
                exchange=self.config['exchange'],
                tradingsymbol=symbol,
                transaction_type="SELL",
                quantity=quantity,
                product=self.config['product_type'],
                order_type=self.config['order_type'],
                validity="DAY"
            )
            
            logger.info(f"SELL Order Placed - ID: {order_id} | Reason: {reason}")
            return order_id
            
        except Exception as e:
            logger.error(f"Error placing SELL order: {e}")
            return None
    
    def get_order_status(self, order_id):
        """Get order status"""
        try:
            orders = self.kite.order_history(order_id)
            if orders:
                return orders[-1]  # Latest status
            return None
        except Exception as e:
            logger.error(f"Error fetching order status: {e}")
            return None
    
    def get_filled_price(self, order_id):
        """Get average filled price for an order"""
        status = self.get_order_status(order_id)
        if status and status.get('status') == 'COMPLETE':
            return status.get('average_price', 0)
        return 0
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TRADE TRACKING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def record_trade(self, entry_price, exit_price, quantity, symbol, exit_reason):
        """Record a completed trade"""
        pnl = (exit_price - entry_price) * quantity
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        
        trade = {
            'trade_number': len(self.daily_trades) + 1,
            'symbol': symbol,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': quantity,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'exit_reason': exit_reason,
            'entry_time': self.entry_time,
            'exit_time': self.get_current_time_ist()
        }
        
        self.daily_trades.append(trade)
        self.total_pnl += pnl
        
        logger.info(f"Trade #{trade['trade_number']} Recorded:")
        logger.info(f"  {symbol} | Entry ₹{entry_price:.2f} → Exit ₹{exit_price:.2f}")
        logger.info(f"  P&L: ₹{pnl:+,.2f} ({pnl_pct:+.2f}%) | Reason: {exit_reason}")
        
        return trade
    
    def get_current_pnl(self):
        """Get current unrealized P&L if position is open"""
        if not self.position_open or not self.selected_option:
            return 0
        
        current_price = self.refresh_option_premium()
        if current_price and self.entry_price:
            return (current_price - self.entry_price) * self.position_quantity
        return 0
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DISPLAY METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def display_status(self, signal_5min=None, signal_2min=None):
        """Display current trading status"""
        now = self.get_current_time_ist()
        nifty_spot = self.get_nifty_spot_price()
        minutes_to_close = self.get_time_to_market_close()
        
        print("\n" + "═" * 80)
        print(f"  NIFTY CE AUTO TRADER - {now.strftime('%Y-%m-%d %H:%M:%S')} IST")
        print(f"  MODE: CONTINUOUS TRADING | TRADE CYCLE #{self.trade_cycle}")
        print("═" * 80)
        
        # Market Status
        market_status = "OPEN" if self.is_market_open() else "CLOSED"
        print(f"\n  MARKET STATUS")
        print("  " + "─" * 76)
        print(f"  Market: {market_status} | Time to Close: {minutes_to_close} minutes")
        
        # Account Status
        print(f"\n  ACCOUNT STATUS")
        print("  " + "─" * 76)
        print(f"  Available Balance: ₹{self.available_balance:,.2f}")
        print(f"  Trading Capital ({self.config['risk_factor']*100:.0f}%): ₹{self.trading_capital:,.2f}")
        
        # Selected Option
        if self.selected_option:
            print(f"\n  SELECTED OPTION (via ADR-003 Scanner)")
            print("  " + "─" * 76)
            print(f"  Symbol: {self.selected_option['tradingsymbol']}")
            print(f"  Strike: {self.selected_option['strike']} (ATM)")
            print(f"  Expiry: {self.expiry_date.strftime('%d-%b-%Y') if self.expiry_date else 'N/A'}")
            print(f"  Current Premium: ₹{self.selected_option['ltp']:.2f}")
            print(f"  Lot Size: {self.config['lot_size']}")
            
            # Quantity Calculation
            print(f"\n  QUANTITY CALCULATION")
            print("  " + "─" * 76)
            cost_per_lot = self.selected_option['ltp'] * self.config['lot_size']
            max_lots = math.floor(self.trading_capital / cost_per_lot) if cost_per_lot > 0 else 0
            print(f"  Cost per Lot: ₹{self.selected_option['ltp']:.2f} × {self.config['lot_size']} = ₹{cost_per_lot:,.2f}")
            print(f"  Max Lots: floor(₹{self.trading_capital:,.2f} / ₹{cost_per_lot:,.2f}) = {max_lots} Lots")
            print(f"  Trading Quantity: {max_lots} × {self.config['lot_size']} = {self.calculated_quantity}")
            print(f"  Total Investment: ₹{self.calculated_quantity * self.selected_option['ltp']:,.2f}")
        
        # Double Confirmation Status
        print(f"\n  DOUBLE CONFIRMATION STATUS (ADR-001)")
        print("  " + "─" * 76)
        print(f"  NIFTY Spot: ₹{nifty_spot:,.2f}")
        
        if signal_5min and signal_2min:
            vals_5 = signal_5min.get('values', {})
            vals_2 = signal_2min.get('values', {})
            
            print(f"\n  | {'Indicator':<14} | {'5-MIN':>7} | {'2-MIN':>7} | {'Status':>7} |")
            print("  |" + "-" * 16 + "|" + "-" * 9 + "|" + "-" * 9 + "|" + "-" * 9 + "|")
            
            # SuperTrend
            st_5 = vals_5.get('supertrend_dir', 'N/A')[:7]
            st_2 = vals_2.get('supertrend_dir', 'N/A')[:7]
            st_ok = "✓" if signal_5min.get('supertrend_bullish') and signal_2min.get('supertrend_bullish') else "✗"
            print(f"  | {'SuperTrend':<14} | {st_5:>7} | {st_2:>7} | {st_ok:>7} |")
            
            # Price > ST
            pst_5 = "YES" if signal_5min.get('close_above_st') else "NO"
            pst_2 = "YES" if signal_2min.get('close_above_st') else "NO"
            pst_ok = "✓" if signal_5min.get('close_above_st') and signal_2min.get('close_above_st') else "✗"
            print(f"  | {'Price > ST':<14} | {pst_5:>7} | {pst_2:>7} | {pst_ok:>7} |")
            
            # EMA Cross
            ema_5 = "8 > 9" if signal_5min.get('ema_bullish') else "8 < 9"
            ema_2 = "8 > 9" if signal_2min.get('ema_bullish') else "8 < 9"
            ema_ok = "✓" if signal_5min.get('ema_bullish') and signal_2min.get('ema_bullish') else "✗"
            print(f"  | {'EMA Cross':<14} | {ema_5:>7} | {ema_2:>7} | {ema_ok:>7} |")
            
            # Price > EMA Lo
            pel_5 = "YES" if signal_5min.get('close_above_ema_low') else "NO"
            pel_2 = "YES" if signal_2min.get('close_above_ema_low') else "NO"
            pel_ok = "✓" if signal_5min.get('close_above_ema_low') and signal_2min.get('close_above_ema_low') else "✗"
            print(f"  | {'Price > EMA Lo':<14} | {pel_5:>7} | {pel_2:>7} | {pel_ok:>7} |")
            
            # StochRSI
            sr_5 = f"{vals_5.get('stoch_rsi', 0):.1f}"
            sr_2 = f"{vals_2.get('stoch_rsi', 0):.1f}"
            sr_ok = "✓" if signal_5min.get('stoch_ok') and signal_2min.get('stoch_ok') else "✗"
            print(f"  | {'StochRSI':<14} | {sr_5:>7} | {sr_2:>7} | {sr_ok:>7} |")
            
            # RSI
            rsi_5 = f"{vals_5.get('rsi', 0):.1f}"
            rsi_2 = f"{vals_2.get('rsi', 0):.1f}"
            rsi_ok = "✓" if signal_5min.get('rsi_ok') and signal_2min.get('rsi_ok') else "✗"
            print(f"  | {'RSI':<14} | {rsi_5:>7} | {rsi_2:>7} | {rsi_ok:>7} |")
            
            # MACD Hist
            mh_5 = f"{vals_5.get('macd_hist', 0):+.2f}"
            mh_2 = f"{vals_2.get('macd_hist', 0):+.2f}"
            mh_ok = "✓" if signal_5min.get('macd_ok') and signal_2min.get('macd_ok') else "✗"
            print(f"  | {'MACD Hist':<14} | {mh_5:>7} | {mh_2:>7} | {mh_ok:>7} |")
            
            print(f"\n  PRIMARY SIGNAL (5-min): {'✓ BUY' if self.primary_signal else '✗ WAIT'}")
            print(f"  CONFIRM SIGNAL (2-min): {'✓ BUY' if self.confirm_signal else '✗ WAIT'}")
        
        # Position Status
        if self.position_open:
            current_pnl = self.get_current_pnl()
            current_price = self.selected_option['ltp'] if self.selected_option else 0
            pnl_pct = ((current_price - self.entry_price) / self.entry_price * 100) if self.entry_price else 0
            
            print("\n" + "═" * 80)
            print(f"  Status: POSITION OPEN | Entry: ₹{self.entry_price:.2f} | "
                  f"Current: ₹{current_price:.2f} | P&L: ₹{current_pnl:+,.2f} ({pnl_pct:+.2f}%)")
        
        # Daily Summary
        if self.daily_trades:
            print(f"\n  DAILY SUMMARY (so far)")
            print("  " + "─" * 76)
            print(f"  Trades Completed: {len(self.daily_trades)}")
            print(f"  Total P&L: ₹{self.total_pnl:+,.2f}")
        
        print("═" * 80)
    
    def display_daily_summary(self):
        """Display end-of-day trading summary"""
        now = self.get_current_time_ist()
        
        print("\n" + "═" * 80)
        print(f"  DAILY TRADING SUMMARY - {now.strftime('%Y-%m-%d')}")
        print("═" * 80)
        print(f"  Total Trades: {len(self.daily_trades)}")
        print(f"  Total P&L: ₹{self.total_pnl:+,.2f}")
        
        if self.daily_trades:
            print(f"\n  TRADE DETAILS:")
            print("  " + "─" * 76)
            
            for trade in self.daily_trades:
                pnl_str = f"₹{trade['pnl']:+,.2f}"
                print(f"  #{trade['trade_number']}: {trade['symbol']} | "
                      f"Entry ₹{trade['entry_price']:.2f} → Exit ₹{trade['exit_price']:.2f} | "
                      f"P&L: {pnl_str} | {trade['exit_reason']}")
        
        print("═" * 80)
        print("  Goodbye!")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN EXECUTION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def execute_buy(self):
        """Execute BUY order with balance check"""
        logger.info("=" * 60)
        logger.info("DOUBLE CONFIRMATION ACHIEVED - EXECUTING BUY ORDER")
        logger.info("=" * 60)
        
        # Step 1: Refresh balance before buying
        self.refresh_balance_before_buy()
        
        # Step 2: Recalculate quantity with fresh balance
        self.refresh_option_premium()
        quantity = self.calculate_quantity()
        
        if quantity <= 0:
            logger.warning("Insufficient balance - waiting 1 minute before retrying")
            return False
        
        # Step 3: Place BUY order
        order_id = self.place_buy_order(
            self.selected_option['tradingsymbol'],
            quantity
        )
        
        if order_id:
            # Wait for order fill
            time.sleep(2)
            filled_price = self.get_filled_price(order_id)
            
            if filled_price > 0:
                self.position_open = True
                self.entry_price = filled_price
                self.entry_time = self.get_current_time_ist()
                self.position_quantity = quantity
                self.position_symbol = self.selected_option['tradingsymbol']
                
                logger.info(f"BUY Executed: {quantity} x {self.position_symbol} @ ₹{filled_price:.2f}")
                return True
            else:
                # Use LTP as fallback
                self.position_open = True
                self.entry_price = self.selected_option['ltp']
                self.entry_time = self.get_current_time_ist()
                self.position_quantity = quantity
                self.position_symbol = self.selected_option['tradingsymbol']
                
                logger.info(f"BUY Executed (LTP): {quantity} x {self.position_symbol} @ ₹{self.entry_price:.2f}")
                return True
        
        return False
    
    def execute_sell(self, reason="manual"):
        """Execute SELL order"""
        if not self.position_open:
            return False
        
        logger.info("=" * 60)
        logger.info(f"EXECUTING SELL ORDER - Reason: {reason}")
        logger.info("=" * 60)
        
        # Get current price before selling
        current_price = self.refresh_option_premium() or self.selected_option['ltp']
        
        # Place SELL order
        order_id = self.place_sell_order(
            self.position_symbol,
            self.position_quantity,
            reason
        )
        
        if order_id:
            # Wait for order fill
            time.sleep(2)
            filled_price = self.get_filled_price(order_id)
            
            exit_price = filled_price if filled_price > 0 else current_price
            
            # Record trade
            self.record_trade(
                entry_price=self.entry_price,
                exit_price=exit_price,
                quantity=self.position_quantity,
                symbol=self.position_symbol,
                exit_reason=reason
            )
            
            # Reset position state
            self.position_open = False
            self.entry_price = 0
            self.entry_time = None
            self.position_quantity = 0
            self.position_symbol = None
            
            logger.info(f"SELL Executed: Exit @ ₹{exit_price:.2f}")
            return True
        
        return False
    
    def wait_for_buy_signal(self):
        """Wait for double confirmation buy signal"""
        last_5min_check = 0
        
        while self.is_running and not self.position_open:
            now = time.time()
            
            # Check market hours
            if not self.is_market_open():
                logger.info("Market closed - stopping signal monitoring")
                return False
            
            # Check if we should stop new trades
            if self.should_stop_new_trades():
                logger.info("Less than 15 minutes to market close - no new trades")
                return False
            
            # Refresh option premium
            self.refresh_option_premium()
            
            # Check 2-minute confirmation (every 5 seconds)
            df_2min = self.get_historical_data("2minute")
            if not df_2min.empty:
                self.confirm_signal, signal_2min = self.check_buy_conditions(df_2min, "2minute")
            else:
                self.confirm_signal = False
                signal_2min = {}
            
            # Check 5-minute primary (every 10 seconds)
            if now - last_5min_check >= self.config['primary_check_seconds']:
                df_5min = self.get_historical_data("5minute")
                if not df_5min.empty:
                    self.primary_signal, signal_5min = self.check_buy_conditions(df_5min, "5minute")
                else:
                    self.primary_signal = False
                    signal_5min = {}
                last_5min_check = now
            else:
                signal_5min = {}
            
            # Display status
            self.display_status(signal_5min, signal_2min)
            
            # Check for double confirmation
            if self.primary_signal and self.confirm_signal:
                return True
            
            # Wait before next check
            time.sleep(self.config['confirm_check_seconds'])
        
        return False
    
    def monitor_for_exit(self):
        """Monitor position for exit conditions"""
        while self.is_running and self.position_open:
            # Check market hours
            if not self.is_market_open():
                logger.info("Market closed - forcing position exit")
                self.execute_sell("market_close")
                return
            
            # Check for market close
            if self.get_time_to_market_close() <= 0:
                logger.info("Market closing - forcing position exit")
                self.execute_sell("market_close")
                return
            
            # Refresh option premium
            self.refresh_option_premium()
            
            # Get 2-minute data for exit check
            df_2min = self.get_historical_data("2minute")
            
            if not df_2min.empty:
                should_exit, exit_reason, exit_details = self.check_exit_conditions(df_2min)
                
                # Display current P&L
                current_pnl = self.get_current_pnl()
                current_price = self.selected_option['ltp'] if self.selected_option else 0
                pnl_pct = ((current_price - self.entry_price) / self.entry_price * 100) if self.entry_price else 0
                
                print(f"\r  Position: {self.position_symbol} | Entry: ₹{self.entry_price:.2f} | "
                      f"Current: ₹{current_price:.2f} | P&L: ₹{current_pnl:+,.2f} ({pnl_pct:+.2f}%)", end="")
                
                if should_exit:
                    print()  # New line
                    self.execute_sell(exit_reason)
                    return
            
            # Wait before next check
            time.sleep(self.config['confirm_check_seconds'])
    
    def run(self, expiry_date=None):
        """
        Main execution loop - continuous trading until market close
        
        Args:
            expiry_date: Expiry date string (e.g., "Jan 23", "2026-01-23")
        """
        self.is_running = True
        
        try:
            # ═══════════════════════════════════════════════════════════════════
            # PHASE 1: INITIALIZATION
            # ═══════════════════════════════════════════════════════════════════
            
            print("\n" + "═" * 80)
            print("  NIFTY CE AUTO TRADER - INITIALIZATION")
            print("═" * 80)
            
            # Get expiry date from user if not provided
            if expiry_date is None:
                expiry_date = self.prompt_for_expiry()
            
            # Parse expiry date
            self.expiry_date = parse_expiry_date(expiry_date)
            logger.info(f"Expiry Date: {self.expiry_date.strftime('%d-%b-%Y')}")
            
            # Get account balance
            self.get_account_balance()
            
            # Check market hours
            if not self.is_market_open():
                logger.warning("Market is currently closed (9:15 AM - 3:30 PM IST)")
                print("\nMarket is closed. Auto Trader will wait for market to open...")
                
                # Wait for market to open
                while not self.is_market_open() and self.is_running:
                    time.sleep(60)  # Check every minute
            
            # ═══════════════════════════════════════════════════════════════════
            # CONTINUOUS TRADING LOOP
            # ═══════════════════════════════════════════════════════════════════
            
            while self.is_running and self.is_market_open():
                self.trade_cycle += 1
                
                logger.info(f"\n{'='*60}")
                logger.info(f"TRADE CYCLE #{self.trade_cycle} STARTING")
                logger.info(f"{'='*60}")
                
                # Check if we should stop new trades
                if self.should_stop_new_trades():
                    logger.info("Less than 15 minutes to market close - stopping new trade cycles")
                    break
                
                # ═══════════════════════════════════════════════════════════════
                # PHASE 2: OPTIONS SCANNER (ADR-003)
                # ═══════════════════════════════════════════════════════════════
                
                # Initialize/refresh scanner
                self.initialize_scanner()
                
                # Select best CE option
                selected = self.select_best_ce_option()
                
                if not selected:
                    logger.warning("No suitable CE option found - waiting 30 seconds")
                    time.sleep(30)
                    continue
                
                # ═══════════════════════════════════════════════════════════════
                # PHASE 3: QUANTITY CALCULATION
                # ═══════════════════════════════════════════════════════════════
                
                # Refresh balance and calculate quantity
                self.get_account_balance()
                quantity = self.calculate_quantity()
                
                if quantity <= 0:
                    logger.warning("Insufficient balance - waiting 1 minute")
                    time.sleep(60)
                    continue
                
                # ═══════════════════════════════════════════════════════════════
                # PHASE 4: WAIT FOR DOUBLE CONFIRMATION (ADR-001)
                # ═══════════════════════════════════════════════════════════════
                
                logger.info("Waiting for Double Confirmation BUY signal...")
                
                if self.wait_for_buy_signal():
                    # ═══════════════════════════════════════════════════════════
                    # PHASE 5: EXECUTE BUY
                    # ═══════════════════════════════════════════════════════════
                    
                    if self.execute_buy():
                        # ═══════════════════════════════════════════════════════
                        # PHASE 6: MONITOR FOR EXIT
                        # ═══════════════════════════════════════════════════════
                        
                        logger.info("Position opened - monitoring for exit conditions...")
                        self.monitor_for_exit()
                    else:
                        # Buy failed (insufficient balance)
                        logger.warning("Buy failed - waiting 1 minute before restart")
                        time.sleep(60)
                
                # ═══════════════════════════════════════════════════════════════
                # PHASE 7: REPEAT CYCLE
                # ═══════════════════════════════════════════════════════════════
                
                if self.is_market_open() and not self.should_stop_new_trades():
                    logger.info("Trade cycle complete - starting new cycle...")
                    time.sleep(5)  # Brief pause before next cycle
            
            # ═══════════════════════════════════════════════════════════════════
            # END OF DAY
            # ═══════════════════════════════════════════════════════════════════
            
            # Force exit any open position
            if self.position_open:
                logger.info("End of trading day - closing open position")
                self.execute_sell("market_close")
            
            # Display daily summary
            self.display_daily_summary()
            
        except KeyboardInterrupt:
            logger.info("\nTrading stopped by user")
            
            # Close any open position
            if self.position_open:
                logger.info("Closing open position...")
                self.execute_sell("user_stop")
            
            self.display_daily_summary()
            
        except Exception as e:
            logger.error(f"Error in trading loop: {e}")
            raise
        
        finally:
            self.is_running = False
    
    def prompt_for_expiry(self):
        """Prompt user for expiry date input"""
        print("\n" + "═" * 80)
        print("  NIFTY CE AUTO TRADER - Configuration")
        print("═" * 80)
        print("\nEnter expiry date in any of these formats:")
        print("  - 'Jan 23' or '23 Jan'")
        print("  - 'Jan 23 2026' or '23 Jan 2026'")
        print("  - '2026-01-23' (ISO format)")
        print("─" * 80)
        
        expiry_input = input("\nEnter Expiry Date (e.g., Jan 23): ").strip()
        
        if not expiry_input:
            raise ValueError("Expiry date is required")
        
        return expiry_input
    
    def stop(self):
        """Stop the trader"""
        self.is_running = False
        logger.info("Trader stopping...")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main entry point"""
    print("\n" + "═" * 80)
    print("  INTEGRATED NIFTY CE AUTO TRADER")
    print("  Based on ADR-004: Options Scanner (ADR-003) + Double Confirmation (ADR-001)")
    print("═" * 80)
    
    try:
        trader = IntegratedNiftyCETrader()
        trader.run()
    except ValueError as e:
        print(f"\nConfiguration Error: {e}")
    except Exception as e:
        print(f"\nError: {e}")
        raise


if __name__ == "__main__":
    main()
