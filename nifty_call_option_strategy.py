"""
NIFTY CE Auto Trader - Integrated Strategy
Implements: ADR-004-INTEGRATED-NIFTY-CE-AUTO-TRADER.md

Strategy Overview:
- Gets account balance to determine position sizing (40% risk factor)
- Takes NIFTY Options Expiry Date as user input
- Uses Options Scanner to select optimal CE options (premium ₹80-₹120)
- Uses Double Confirmation Strategy (5-min + 2-min) for entries
- Exits on: EMA Low Falling OR Strong Bearish Signal OR Market Close
- Repeats trading cycle until market closes (3:30 PM IST)
- Skips first 15 minutes (9:15-9:30 AM) - volatile opening

Author: Trading System Team
Date: January 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
from kiteconnect import KiteConnect
import logging
import sys
import time as time_module
import math
import pytz

# Import config
from config import KITE_API_KEY, KITE_ACCESS_TOKEN

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# IST Timezone
IST = pytz.timezone('Asia/Kolkata')


# ============== CONFIGURATION (ADR-004) ==============

class TraderConfig:
    """Configuration for Integrated NIFTY CE Auto Trader (ADR-004)"""
    
    # Options Scanner (ADR-003)
    STRIKE_MIN = 25000
    STRIKE_MAX = 26000
    STRIKE_MULTIPLE = 100
    PREMIUM_MIN = 80
    PREMIUM_MAX = 120
    SCANNER_REFRESH_SECONDS = 5
    
    # Quantity Calculation
    RISK_FACTOR = 0.40          # Use 40% of balance
    LOT_SIZE = 75               # NIFTY lot size
    
    # Market Hours (IST)
    MARKET_OPEN_HOUR = 9
    MARKET_OPEN_MINUTE = 15
    MARKET_CLOSE_HOUR = 15
    MARKET_CLOSE_MINUTE = 30
    SKIP_FIRST_MINUTES = 15     # Skip 9:15-9:30 AM (volatile opening)
    STOP_NEW_TRADES_MINUTES = 15  # Stop new trades 15 min before close
    
    # Double Confirmation (ADR-001)
    PRIMARY_TIMEFRAME = "5minute"
    CONFIRM_TIMEFRAME = "2minute"
    PRIMARY_CHECK_SECONDS = 10
    CONFIRM_CHECK_SECONDS = 5
    
    # Indicator Parameters
    SUPERTREND_PERIOD = 7
    SUPERTREND_MULTIPLIER = 3
    EMA_LOW_PERIOD = 8
    EMA_LOW_OFFSET = 9
    EMA_FAST = 8
    EMA_SLOW = 9
    RSI_PERIOD = 14
    MACD_FAST = 5
    MACD_SLOW = 13
    MACD_SIGNAL = 6
    
    # Trading
    EXCHANGE = "NFO"
    PRODUCT_TYPE = "MIS"        # Intraday
    ORDER_TYPE = "MARKET"
    
    # Continuous Trading
    CONTINUOUS_MODE = True


# ============== INDICATOR CALCULATIONS ==============

def ema(data, period):
    """Exponential Moving Average"""
    return pd.Series(data).ewm(span=period, adjust=False).mean().values


def atr(high, low, close, period=14):
    """Average True Range"""
    high = pd.Series(high)
    low = pd.Series(low)
    close = pd.Series(close)
    
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.ewm(span=period, adjust=False).mean().values


def supertrend(high, low, close, period=7, multiplier=3):
    """SuperTrend (7, 3) - Primary trend identification"""
    high = pd.Series(high)
    low = pd.Series(low)
    close = pd.Series(close)
    
    atr_values = pd.Series(atr(high, low, close, period))
    hl2 = (high + low) / 2
    
    basic_upper = hl2 + (multiplier * atr_values)
    basic_lower = hl2 - (multiplier * atr_values)
    
    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    supertrend_arr = pd.Series(index=close.index, dtype=float)
    trend = pd.Series(index=close.index, dtype=int)
    
    for i in range(1, len(close)):
        if basic_upper.iloc[i] < final_upper.iloc[i-1] or close.iloc[i-1] > final_upper.iloc[i-1]:
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i-1]
        
        if basic_lower.iloc[i] > final_lower.iloc[i-1] or close.iloc[i-1] < final_lower.iloc[i-1]:
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i-1]
    
    for i in range(1, len(close)):
        if i == 1:
            trend.iloc[i] = 1 if close.iloc[i] > final_upper.iloc[i] else -1
        else:
            if trend.iloc[i-1] == -1 and close.iloc[i] > final_upper.iloc[i]:
                trend.iloc[i] = 1
            elif trend.iloc[i-1] == 1 and close.iloc[i] < final_lower.iloc[i]:
                trend.iloc[i] = -1
            else:
                trend.iloc[i] = trend.iloc[i-1]
        
        supertrend_arr.iloc[i] = final_lower.iloc[i] if trend.iloc[i] == 1 else final_upper.iloc[i]
    
    return supertrend_arr.values, trend.values


def ema_on_low(low_prices, period=8):
    """EMA on Low prices - Support level tracking"""
    return pd.Series(low_prices).ewm(span=period, adjust=False).mean().values


def rsi(data, period=14):
    """RSI (14) - Overbought/oversold indicator"""
    delta = pd.Series(data).diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return (100 - (100 / (1 + rs))).values


def stochastic_rsi(data, rsi_period=14, stoch_period=14, smooth_k=3, smooth_d=3):
    """Stochastic RSI - Momentum indicator"""
    rsi_values = pd.Series(rsi(data, rsi_period))
    lowest = rsi_values.rolling(window=stoch_period).min()
    highest = rsi_values.rolling(window=stoch_period).max()
    stoch_rsi = ((rsi_values - lowest) / (highest - lowest)) * 100
    k = stoch_rsi.rolling(window=smooth_k).mean()
    d = k.rolling(window=smooth_d).mean()
    return k.values, d.values


def macd(data, fast=5, slow=13, signal=6):
    """MACD (5, 13, 6) - Momentum confirmation"""
    prices = pd.Series(data)
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line.values, signal_line.values, histogram.values


def calculate_indicators(df):
    """Calculate all indicators for NIFTY analysis"""
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    
    df['supertrend'], df['supertrend_direction'] = supertrend(high, low, close, 7, 3)
    df['ema_low_8'] = ema_on_low(low, 8)
    df['ema_8'] = ema(close, 8)
    df['ema_9'] = ema(close, 9)
    df['rsi_14'] = rsi(close, 14)
    df['stoch_rsi_k'], df['stoch_rsi_d'] = stochastic_rsi(close)
    df['macd'], df['macd_signal'], df['macd_hist'] = macd(close, 5, 13, 6)
    
    return df


# ============== INTEGRATED NIFTY CE AUTO TRADER ==============

class IntegratedNiftyCETrader:
    """
    Integrated NIFTY CE Auto Trader (ADR-004)
    
    Combines:
    - ADR-003: Options Scanner (premium ₹80-₹120)
    - ADR-001: Double Confirmation Strategy
    
    Features:
    - Balance-based position sizing (40% risk factor)
    - Continuous trading until market close
    - Market hours enforcement (9:15 AM - 3:30 PM IST)
    - Skip first 15 minutes (volatile opening)
    - Daily trade tracking and summary
    """
    
    def __init__(self, simulation=True):
        self.kite = None
        self.simulation = simulation
        self.config = TraderConfig()
        
        # State
        self.position = None
        self.expiry_date = None
        self.selected_option = None
        self.nfo_instruments = None
        
        # Daily tracking
        self.trade_cycle = 0
        self.daily_trades = []
        self.daily_pnl = 0.0
        
        # Balance
        self.available_balance = 0.0
        self.trading_capital = 0.0
    
    def initialize(self):
        """Initialize Kite Connect and load data"""
        logger.info("Initializing Kite Connect...")
        self.kite = KiteConnect(api_key=KITE_API_KEY)
        
        if KITE_ACCESS_TOKEN:
            self.kite.set_access_token(KITE_ACCESS_TOKEN)
            logger.info("Access token set from config")
        else:
            logger.error("No access token found. Please run auth_helper.py first")
            sys.exit(1)
        
        # Test connection
        try:
            profile = self.kite.profile()
            logger.info(f"Connected as: {profile['user_name']} ({profile['user_id']})")
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            sys.exit(1)
        
        # Load NFO instruments
        logger.info("Loading NFO instruments...")
        self.nfo_instruments = self.kite.instruments("NFO")
        logger.info(f"Loaded {len(self.nfo_instruments)} NFO instruments")
    
    # ============== MARKET HOURS METHODS ==============
    
    def get_current_ist_time(self):
        """Get current time in IST"""
        return datetime.now(IST)
    
    def is_trading_day(self):
        """Check if today is a trading day (Monday-Friday)"""
        now = self.get_current_ist_time()
        # 0 = Monday, 6 = Sunday
        return now.weekday() < 5  # Monday to Friday
    
    def is_market_open(self):
        """Check if market is currently open (9:15 AM - 3:30 PM IST, Mon-Fri)"""
        now = self.get_current_ist_time()
        
        # Check if it's a weekday first
        if not self.is_trading_day():
            return False
        
        market_open = now.replace(hour=self.config.MARKET_OPEN_HOUR, 
                                   minute=self.config.MARKET_OPEN_MINUTE, 
                                   second=0, microsecond=0)
        market_close = now.replace(hour=self.config.MARKET_CLOSE_HOUR,
                                    minute=self.config.MARKET_CLOSE_MINUTE,
                                    second=0, microsecond=0)
        return market_open <= now <= market_close
    
    def is_opening_period(self):
        """Check if within first 15 minutes (9:15-9:30 AM) - skip trading"""
        now = self.get_current_ist_time()
        market_open = now.replace(hour=self.config.MARKET_OPEN_HOUR,
                                   minute=self.config.MARKET_OPEN_MINUTE,
                                   second=0, microsecond=0)
        skip_end = market_open + timedelta(minutes=self.config.SKIP_FIRST_MINUTES)
        return market_open <= now < skip_end
    
    def should_stop_new_trades(self):
        """Check if < 15 minutes to market close"""
        now = self.get_current_ist_time()
        market_close = now.replace(hour=self.config.MARKET_CLOSE_HOUR,
                                    minute=self.config.MARKET_CLOSE_MINUTE,
                                    second=0, microsecond=0)
        stop_time = market_close - timedelta(minutes=self.config.STOP_NEW_TRADES_MINUTES)
        return now >= stop_time
    
    def get_time_to_market_close(self):
        """Return minutes remaining until market closes"""
        now = self.get_current_ist_time()
        market_close = now.replace(hour=self.config.MARKET_CLOSE_HOUR,
                                    minute=self.config.MARKET_CLOSE_MINUTE,
                                    second=0, microsecond=0)
        delta = market_close - now
        return max(0, int(delta.total_seconds() / 60))
    
    # ============== BALANCE & QUANTITY METHODS ==============
    
    def get_account_balance(self):
        """Fetch available balance from kite.margins()"""
        try:
            margins = self.kite.margins(segment="equity")
            self.available_balance = margins['available']['live_balance']
            self.trading_capital = self.available_balance * self.config.RISK_FACTOR
            logger.info(f"Available Balance: ₹{self.available_balance:,.2f}")
            logger.info(f"Trading Capital ({self.config.RISK_FACTOR*100:.0f}%): ₹{self.trading_capital:,.2f}")
            return self.available_balance
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return 0
    
    def calculate_quantity(self, premium):
        """Calculate quantity based on balance and premium"""
        if premium <= 0:
            return 0
        
        cost_per_lot = premium * self.config.LOT_SIZE
        max_lots = math.floor(self.trading_capital / cost_per_lot)
        quantity = max_lots * self.config.LOT_SIZE
        
        logger.info(f"Cost per Lot: ₹{premium:.2f} × {self.config.LOT_SIZE} = ₹{cost_per_lot:,.2f}")
        logger.info(f"Max Lots: floor(₹{self.trading_capital:,.2f} / ₹{cost_per_lot:,.2f}) = {max_lots}")
        logger.info(f"Quantity: {max_lots} × {self.config.LOT_SIZE} = {quantity}")
        
        return quantity
    
    # ============== OPTIONS SCANNER METHODS (ADR-003) ==============
    
    def get_nifty_spot_price(self):
        """Get current NIFTY index price"""
        try:
            quote = self.kite.ltp(["NSE:NIFTY 50"])
            return quote["NSE:NIFTY 50"]["last_price"]
        except Exception as e:
            logger.error(f"Error fetching NIFTY LTP: {e}")
            return None
    
    def get_expiry_date_input(self):
        """Accept and parse user expiry date input"""
        print("\n" + "="*60)
        print("  ENTER EXPIRY DATE")
        print("="*60)
        print("  Format: YYYY-MM-DD (e.g., 2026-01-23)")
        print("  Or: Jan 23, Feb 06, etc.")
        print("="*60)
        
        while True:
            user_input = input("\n  Expiry Date: ").strip()
            
            # Try parsing different formats
            try:
                # Try YYYY-MM-DD
                expiry = datetime.strptime(user_input, "%Y-%m-%d").date()
                self.expiry_date = expiry
                logger.info(f"Expiry date set: {expiry}")
                return expiry
            except ValueError:
                pass
            
            try:
                # Try "Jan 23" format
                current_year = datetime.now().year
                expiry = datetime.strptime(f"{user_input} {current_year}", "%b %d %Y").date()
                self.expiry_date = expiry
                logger.info(f"Expiry date set: {expiry}")
                return expiry
            except ValueError:
                pass
            
            print("  Invalid format. Please try again.")
    
    def load_nifty_options(self):
        """Load NIFTY options for selected expiry"""
        if not self.expiry_date:
            logger.error("Expiry date not set")
            return []
        
        options = []
        for inst in self.nfo_instruments:
            if (inst['name'] == 'NIFTY' and 
                inst['instrument_type'] == 'CE' and
                inst['expiry'] == self.expiry_date and
                self.config.STRIKE_MIN <= inst['strike'] <= self.config.STRIKE_MAX and
                inst['strike'] % self.config.STRIKE_MULTIPLE == 0):
                options.append(inst)
        
        logger.info(f"Found {len(options)} NIFTY CE options for {self.expiry_date}")
        return options
    
    def filter_by_premium_range(self, options):
        """Filter options with premium in range ₹80-₹120"""
        if not options:
            return []
        
        # Get LTP for all options
        symbols = [f"NFO:{opt['tradingsymbol']}" for opt in options]
        
        try:
            quotes = self.kite.ltp(symbols)
        except Exception as e:
            logger.error(f"Error fetching option quotes: {e}")
            return []
        
        filtered = []
        for opt in options:
            symbol = f"NFO:{opt['tradingsymbol']}"
            if symbol in quotes:
                ltp = quotes[symbol]['last_price']
                if self.config.PREMIUM_MIN <= ltp <= self.config.PREMIUM_MAX:
                    opt['ltp'] = ltp
                    filtered.append(opt)
        
        logger.info(f"Filtered to {len(filtered)} options with premium ₹{self.config.PREMIUM_MIN}-₹{self.config.PREMIUM_MAX}")
        return filtered
    
    def select_best_ce_option(self):
        """Select best CE option (ATM or closest to ₹100 premium)"""
        # Load options
        options = self.load_nifty_options()
        if not options:
            logger.warning("No options found for selected expiry")
            return None
        
        # Filter by premium range
        filtered = self.filter_by_premium_range(options)
        if not filtered:
            logger.warning("No options in premium range ₹80-₹120")
            return None
        
        # Get NIFTY spot price
        nifty_spot = self.get_nifty_spot_price()
        if not nifty_spot:
            return None
        
        # Calculate ATM strike
        atm_strike = round(nifty_spot / 100) * 100
        logger.info(f"NIFTY Spot: ₹{nifty_spot:.2f} | ATM Strike: {atm_strike}")
        
        # Priority 1: ATM if in range
        for opt in filtered:
            if opt['strike'] == atm_strike:
                self.selected_option = opt
                logger.info(f"Selected ATM: {opt['tradingsymbol']} @ ₹{opt['ltp']:.2f}")
                return opt
        
        # Priority 2: Closest to ATM with premium closest to ₹100
        best_option = min(filtered, key=lambda x: (abs(x['strike'] - atm_strike), abs(x['ltp'] - 100)))
        self.selected_option = best_option
        logger.info(f"Selected: {best_option['tradingsymbol']} | Strike: {best_option['strike']} | Premium: ₹{best_option['ltp']:.2f}")
        return best_option
    
    def get_option_ltp(self, instrument_token=None):
        """Get option last traded price"""
        if not self.selected_option and not instrument_token:
            return None
        
        token = instrument_token or self.selected_option['instrument_token']
        symbol = f"NFO:{self.selected_option['tradingsymbol']}" if not instrument_token else None
        
        try:
            if symbol:
                quote = self.kite.ltp([symbol])
                return quote[symbol]['last_price']
            else:
                # Use instrument token
                for inst in self.nfo_instruments:
                    if inst['instrument_token'] == token:
                        symbol = f"NFO:{inst['tradingsymbol']}"
                        quote = self.kite.ltp([symbol])
                        return quote[symbol]['last_price']
        except Exception as e:
            logger.error(f"Error fetching option LTP: {e}")
        return None
    
    # ============== DOUBLE CONFIRMATION METHODS (ADR-001) ==============
    
    def fetch_nifty_historical(self, interval="2minute", days=5):
        """Fetch NIFTY historical data for indicator calculation
        
        Uses 5 days by default to cover weekends (Mon needs Fri data)
        """
        try:
            nifty_token = 256265  # NIFTY 50 token
            
            # Use IST timezone for accurate dates
            now_ist = self.get_current_ist_time()
            to_date = now_ist
            from_date = to_date - timedelta(days=days)
            
            data = self.kite.historical_data(
                instrument_token=nifty_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            
            df = pd.DataFrame(data)
            
            # Debug: Log how many candles we got
            logger.info(f"Historical data: {len(df)} candles ({interval}) from {from_date.date()} to {to_date.date()}")
            
            if len(df) > 0 and df['date'].dt.tz is not None:
                df['date'] = df['date'].dt.tz_localize(None)
            
            return df
        except Exception as e:
            logger.error(f"Error fetching NIFTY historical data: {e}")
            return None
    
    def resample_to_5min(self, df_2min):
        """Resample 2-minute data to 5-minute"""
        df = df_2min.copy()
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        
        resampled = df.resample('5min').agg(agg_dict).dropna()
        resampled.reset_index(inplace=True)
        return resampled
    
    def check_buy_conditions(self, df):
        """
        Check BUY conditions (ADR-001 Double Confirmation)
        
        All conditions must be true:
        - SuperTrend (7,3) Bullish + Price > SuperTrend
        - Price > EMA Low (8)
        - EMA 8 > EMA 9 (bullish crossover)
        - StochRSI < 50 OR rising
        - RSI < 65 AND rising
        - MACD histogram > 0 OR improving
        """
        if len(df) < 3:
            return False, {}
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        conditions = {
            'supertrend_bullish': curr['supertrend_direction'] == 1,
            'price_above_st': curr['close'] > curr['supertrend'],
            'price_above_ema_low': curr['close'] > curr['ema_low_8'],
            'ema_bullish': curr['ema_8'] > curr['ema_9'],
            'stoch_rsi_good': curr['stoch_rsi_k'] < 50 or curr['stoch_rsi_k'] > prev['stoch_rsi_k'],
            'rsi_good': curr['rsi_14'] < 65 and curr['rsi_14'] > prev['rsi_14'],
            'macd_good': curr['macd_hist'] > 0 or curr['macd_hist'] > prev['macd_hist'],
        }
        
        all_met = all([
            conditions['supertrend_bullish'],
            conditions['price_above_st'],
            conditions['price_above_ema_low'],
            conditions['ema_bullish'],
            conditions['stoch_rsi_good'],
            conditions['macd_good']
        ])
        
        return all_met, conditions
    
    def check_exit_conditions(self, df):
        """
        Check EXIT conditions (ADR-001)
        
        EXIT TRIGGER 1: EMA Low Falling
        - ema_low_falling AND price_below_ema
        
        EXIT TRIGGER 2: Strong Bearish
        - supertrend_direction == -1 AND ema_8 < ema_9 AND close < ema_low_8
        """
        if len(df) < 3:
            return False, None
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3]
        
        # EXIT TRIGGER 1: EMA Low Falling
        ema_low_falling = (curr['ema_low_8'] < prev['ema_low_8'] and 
                          prev['ema_low_8'] < prev2['ema_low_8'])
        price_below_ema = curr['close'] < curr['ema_low_8']
        trigger_1 = ema_low_falling and price_below_ema
        
        # EXIT TRIGGER 2: Strong Bearish
        trigger_2 = (curr['supertrend_direction'] == -1 and
                     curr['ema_8'] < curr['ema_9'] and
                     curr['close'] < curr['ema_low_8'])
        
        if trigger_1:
            return True, "EMA_LOW_FALLING"
        elif trigger_2:
            return True, "STRONG_BEARISH"
        
        return False, None
    
    # ============== ORDER EXECUTION ==============
    
    def place_buy_order(self, symbol, quantity):
        """Place CALL option buy order"""
        if self.simulation:
            logger.info(f"[SIMULATION] BUY {quantity} of {symbol}")
            return True, "SIM_ORDER_001"
        else:
            try:
                order_id = self.kite.place_order(
                    variety=self.kite.VARIETY_REGULAR,
                    exchange=self.kite.EXCHANGE_NFO,
                    tradingsymbol=symbol,
                    transaction_type=self.kite.TRANSACTION_TYPE_BUY,
                    quantity=quantity,
                    product=self.kite.PRODUCT_MIS,
                    order_type=self.kite.ORDER_TYPE_MARKET
                )
                logger.info(f"BUY Order placed: {order_id}")
                return True, order_id
            except Exception as e:
                logger.error(f"BUY Order failed: {e}")
                return False, None
    
    def place_sell_order(self, symbol, quantity, reason):
        """Place CALL option sell order"""
        if self.simulation:
            logger.info(f"[SIMULATION] SELL {quantity} of {symbol} - Reason: {reason}")
            return True, "SIM_ORDER_002"
        else:
            try:
                order_id = self.kite.place_order(
                    variety=self.kite.VARIETY_REGULAR,
                    exchange=self.kite.EXCHANGE_NFO,
                    tradingsymbol=symbol,
                    transaction_type=self.kite.TRANSACTION_TYPE_SELL,
                    quantity=quantity,
                    product=self.kite.PRODUCT_MIS,
                    order_type=self.kite.ORDER_TYPE_MARKET
                )
                logger.info(f"SELL Order placed: {order_id} - Reason: {reason}")
                return True, order_id
            except Exception as e:
                logger.error(f"SELL Order failed: {e}")
                return False, None
    
    # ============== DISPLAY & LOGGING ==============
    
    def display_status(self, nifty_spot, df_5min, df_2min, primary_signal, confirm_signal):
        """Display current trading status"""
        now = self.get_current_ist_time()
        
        print("\n" + "="*80)
        print(f"  NIFTY CE AUTO TRADER - {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  MODE: {'SIMULATION' if self.simulation else 'LIVE'} | TRADE CYCLE #{self.trade_cycle}")
        print("="*80)
        
        # Market Status
        print("\n  MARKET STATUS")
        print("  " + "-"*76)
        market_status = "OPEN" if self.is_market_open() else "CLOSED"
        time_to_close = self.get_time_to_market_close()
        print(f"  Market: {market_status} | Time to Close: {time_to_close} minutes")
        
        if self.is_opening_period():
            print("  *** SKIP ZONE: First 15 minutes (9:15-9:30 AM) - Waiting... ***")
        
        # Account Status
        print("\n  ACCOUNT STATUS")
        print("  " + "-"*76)
        print(f"  Available Balance: ₹{self.available_balance:,.2f}")
        print(f"  Trading Capital ({self.config.RISK_FACTOR*100:.0f}%): ₹{self.trading_capital:,.2f}")
        
        # Selected Option
        if self.selected_option:
            print("\n  SELECTED OPTION (via Scanner)")
            print("  " + "-"*76)
            print(f"  Symbol: {self.selected_option['tradingsymbol']}")
            print(f"  Strike: {self.selected_option['strike']}")
            print(f"  Expiry: {self.expiry_date}")
            print(f"  Premium: ₹{self.selected_option.get('ltp', 0):.2f}")
        
        # Double Confirmation Status
        if df_5min is not None and df_2min is not None and len(df_5min) > 0 and len(df_2min) > 0:
            curr_5m = df_5min.iloc[-1]
            curr_2m = df_2min.iloc[-1]
            
            print("\n  DOUBLE CONFIRMATION STATUS")
            print("  " + "-"*76)
            print(f"  NIFTY Spot: ₹{nifty_spot:,.2f}")
            print()
            
            st_5m = "BULLISH" if curr_5m['supertrend_direction'] == 1 else "BEARISH"
            st_2m = "BULLISH" if curr_2m['supertrend_direction'] == 1 else "BEARISH"
            ema_5m = "8 > 9" if curr_5m['ema_8'] > curr_5m['ema_9'] else "8 < 9"
            ema_2m = "8 > 9" if curr_2m['ema_8'] > curr_2m['ema_9'] else "8 < 9"
            
            print(f"  | {'Indicator':<14} | {'5-MIN':<8} | {'2-MIN':<8} |")
            print(f"  |{'-'*16}|{'-'*10}|{'-'*10}|")
            print(f"  | {'SuperTrend':<14} | {st_5m:<8} | {st_2m:<8} |")
            print(f"  | {'EMA Cross':<14} | {ema_5m:<8} | {ema_2m:<8} |")
            print(f"  | {'RSI':<14} | {curr_5m['rsi_14']:<8.1f} | {curr_2m['rsi_14']:<8.1f} |")
            print(f"  | {'StochRSI':<14} | {curr_5m['stoch_rsi_k']:<8.1f} | {curr_2m['stoch_rsi_k']:<8.1f} |")
            print(f"  | {'MACD Hist':<14} | {curr_5m['macd_hist']:<8.2f} | {curr_2m['macd_hist']:<8.2f} |")
            print()
            
            primary_status = "BUY" if primary_signal else "WAIT"
            confirm_status = "BUY" if confirm_signal else "WAIT"
            print(f"  PRIMARY SIGNAL (5-min): {primary_status}")
            print(f"  CONFIRM SIGNAL (2-min): {confirm_status}")
        
        # Position Status
        if self.position:
            current_premium = self.get_option_ltp()
            if current_premium:
                pnl = (current_premium - self.position['entry_price']) * self.position['quantity']
                pnl_pct = ((current_premium - self.position['entry_price']) / self.position['entry_price']) * 100
                
                print("\n" + "="*80)
                pnl_icon = "+" if pnl >= 0 else ""
                print(f"  POSITION OPEN | Entry: ₹{self.position['entry_price']:.2f} | "
                      f"Current: ₹{current_premium:.2f} | P&L: {pnl_icon}₹{pnl:.2f} ({pnl_pct:+.2f}%)")
                print("="*80)
        
        # Daily Summary
        if self.daily_trades:
            print(f"\n  Daily P&L: ₹{self.daily_pnl:,.2f} | Trades: {len(self.daily_trades)}")
    
    def display_daily_summary(self):
        """Display end-of-day trading summary"""
        print("\n" + "="*80)
        print(f"  DAILY TRADING SUMMARY - {datetime.now().strftime('%Y-%m-%d')}")
        print("="*80)
        print(f"  Total Trades: {len(self.daily_trades)}")
        print(f"  Total P&L: ₹{self.daily_pnl:,.2f}")
        
        if self.daily_trades:
            print("\n  TRADE DETAILS:")
            print("  " + "-"*76)
            for i, trade in enumerate(self.daily_trades, 1):
                pnl_icon = "+" if trade['pnl'] >= 0 else ""
                print(f"  #{i}: {trade['symbol']} | Entry ₹{trade['entry_price']:.2f} → "
                      f"Exit ₹{trade['exit_price']:.2f} | P&L: {pnl_icon}₹{trade['pnl']:.2f} | {trade['exit_reason']}")
        
        print("="*80)
        print("  Session ended. Goodbye!")
        print("="*80)
    
    def log_trade(self, entry_price, exit_price, quantity, exit_reason):
        """Log completed trade to daily summary"""
        pnl = (exit_price - entry_price) * quantity
        self.daily_pnl += pnl
        
        trade = {
            'symbol': self.position['symbol'],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': quantity,
            'pnl': pnl,
            'exit_reason': exit_reason,
            'timestamp': datetime.now()
        }
        self.daily_trades.append(trade)
        
        logger.info(f"Trade logged: {trade['symbol']} | P&L: ₹{pnl:.2f} | Reason: {exit_reason}")
    
    # ============== MAIN EXECUTION ==============
    
    def run(self, expiry_date=None):
        """Main trading loop"""
        print("""
╔═══════════════════════════════════════════════════════════════════════════════╗
║           INTEGRATED NIFTY CE AUTO TRADER (ADR-004)                           ║
║           Double Confirmation Strategy + Options Scanner                       ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Strategy:
• Premium Range: ₹80-₹120 | Risk Factor: 40%
• Entry: Double Confirmation (5-min + 2-min)
• Exit: EMA Low Falling OR Strong Bearish OR Market Close
• Skip: First 15 minutes (9:15-9:30 AM)
• Stop: 15 minutes before market close (3:15 PM)

Press Ctrl+C to stop.
""")
        
        # Initialize
        self.initialize()
        
        # Get expiry date from user or command line
        if expiry_date:
            # Parse command line expiry
            try:
                self.expiry_date = datetime.strptime(expiry_date, "%Y-%m-%d").date()
            except ValueError:
                try:
                    current_year = datetime.now().year
                    self.expiry_date = datetime.strptime(f"{expiry_date} {current_year}", "%b %d %Y").date()
                except ValueError:
                    logger.error(f"Invalid expiry date format: {expiry_date}")
                    self.get_expiry_date_input()
            logger.info(f"Expiry date set: {self.expiry_date}")
        else:
            self.get_expiry_date_input()
        
        # Get initial balance
        self.get_account_balance()
        
        # Main loop
        while True:
            try:
                # Check if it's a trading day (Mon-Fri)
                if not self.is_trading_day():
                    now = self.get_current_ist_time()
                    day_name = now.strftime("%A")
                    logger.warning(f"Today is {day_name} - Market is CLOSED. No trading on weekends.")
                    print(f"\n  Today is {day_name}. Indian markets are closed on weekends.")
                    print("  Please run this on a trading day (Monday-Friday).")
                    print("  Exiting...")
                    break
                
                # Check market hours
                if not self.is_market_open():
                    logger.info("Market is closed. Waiting...")
                    if self.daily_trades:
                        self.display_daily_summary()
                        break
                    time_module.sleep(60)
                    continue
                
                # Skip opening period (first 15 minutes)
                if self.is_opening_period():
                    logger.info("Opening period (9:15-9:30 AM) - Skipping...")
                    time_module.sleep(10)
                    continue
                
                # Increment trade cycle if no position
                if not self.position:
                    self.trade_cycle += 1
                
                # Refresh balance before each cycle
                if not self.position:
                    self.get_account_balance()
                
                # Select option via scanner
                if not self.selected_option or not self.position:
                    self.select_best_ce_option()
                
                if not self.selected_option:
                    logger.warning("No suitable option found. Waiting...")
                    time_module.sleep(30)
                    continue
                
                # Fetch NIFTY data
                df_2min = self.fetch_nifty_historical("2minute", days=2)
                if df_2min is None or len(df_2min) < 20:
                    logger.warning("Insufficient data, waiting...")
                    time_module.sleep(5)
                    continue
                
                # Calculate indicators
                df_2min = calculate_indicators(df_2min)
                df_5min = self.resample_to_5min(df_2min)
                df_5min = calculate_indicators(df_5min)
                
                # Get NIFTY spot
                nifty_spot = self.get_nifty_spot_price()
                if not nifty_spot:
                    time_module.sleep(5)
                    continue
                
                # Check signals
                primary_signal, _ = self.check_buy_conditions(df_5min)
                confirm_signal, _ = self.check_buy_conditions(df_2min)
                
                # Display status
                self.display_status(nifty_spot, df_5min, df_2min, primary_signal, confirm_signal)
                
                # Position management
                if self.position:
                    # Get current premium
                    current_premium = self.get_option_ltp()
                    if not current_premium:
                        time_module.sleep(5)
                        continue
                    
                    # Check exit conditions
                    should_exit, exit_reason = self.check_exit_conditions(df_2min)
                    
                    # Force exit at market close
                    if self.get_time_to_market_close() <= 0:
                        should_exit = True
                        exit_reason = "MARKET_CLOSE"
                    
                    if should_exit:
                        print("\n" + "="*80)
                        print(f"  >>> EXIT SIGNAL: {exit_reason} <<<")
                        print("="*80)
                        
                        # Place sell order
                        success, order_id = self.place_sell_order(
                            self.position['symbol'],
                            self.position['quantity'],
                            exit_reason
                        )
                        
                        if success:
                            # Log trade
                            self.log_trade(
                                self.position['entry_price'],
                                current_premium,
                                self.position['quantity'],
                                exit_reason
                            )
                            
                            pnl = (current_premium - self.position['entry_price']) * self.position['quantity']
                            print(f"  Entry: ₹{self.position['entry_price']:.2f} | Exit: ₹{current_premium:.2f}")
                            print(f"  P&L: {'+'if pnl >= 0 else ''}₹{pnl:.2f}")
                            print("="*80)
                            
                            # Clear position
                            self.position = None
                            self.selected_option = None
                            
                            # Check if should continue
                            if self.should_stop_new_trades():
                                logger.info("Stopping new trades (15 min before close)")
                                self.display_daily_summary()
                                break
                            
                            # Continue to next cycle
                            continue
                
                # Entry logic (no position)
                elif primary_signal and confirm_signal:
                    # Double confirmation achieved
                    if self.should_stop_new_trades():
                        logger.info("Skipping entry - too close to market close")
                        time_module.sleep(30)
                        continue
                    
                    print("\n" + "="*80)
                    print("  >>> DOUBLE CONFIRMATION - EXECUTING BUY <<<")
                    print("="*80)
                    
                    # Refresh balance
                    self.get_account_balance()
                    
                    # Refresh option premium
                    current_premium = self.get_option_ltp()
                    if not current_premium:
                        logger.warning("Could not get premium")
                        time_module.sleep(5)
                        continue
                    
                    self.selected_option['ltp'] = current_premium
                    
                    # Calculate quantity
                    quantity = self.calculate_quantity(current_premium)
                    
                    if quantity <= 0:
                        logger.warning("Insufficient balance - waiting 1 minute")
                        time_module.sleep(60)
                        continue
                    
                    # Place buy order
                    success, order_id = self.place_buy_order(
                        self.selected_option['tradingsymbol'],
                        quantity
                    )
                    
                    if success:
                        self.position = {
                            'symbol': self.selected_option['tradingsymbol'],
                            'instrument_token': self.selected_option['instrument_token'],
                            'strike': self.selected_option['strike'],
                            'entry_price': current_premium,
                            'entry_time': datetime.now(),
                            'quantity': quantity,
                            'order_id': order_id
                        }
                        
                        total_investment = current_premium * quantity
                        print(f"\n  Symbol: {self.position['symbol']}")
                        print(f"  Quantity: {quantity}")
                        print(f"  Entry Price: ₹{current_premium:.2f}")
                        print(f"  Total Investment: ₹{total_investment:,.2f}")
                        print("="*80)
                
                elif primary_signal:
                    logger.info("5-MIN ready, waiting for 2-MIN confirmation...")
                elif confirm_signal:
                    logger.info("2-MIN ready, waiting for 5-MIN confirmation...")
                
                # Sleep
                time_module.sleep(self.config.CONFIRM_CHECK_SECONDS)
                
            except KeyboardInterrupt:
                logger.info("\n\nStrategy stopped by user")
                if self.position:
                    logger.warning(f"Open position: {self.position['symbol']}")
                self.display_daily_summary()
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time_module.sleep(5)


# ============== MAIN ==============

def main():
    """Main function to run Integrated NIFTY CE Auto Trader"""
    import argparse
    
    parser = argparse.ArgumentParser(description='NIFTY CE Auto Trader (ADR-004)')
    parser.add_argument('--live', action='store_true', help='Run in LIVE trading mode (real orders)')
    parser.add_argument('--simulation', action='store_true', help='Run in SIMULATION mode (no real orders)')
    parser.add_argument('--test', action='store_true', help='Test connection only')
    parser.add_argument('--expiry', type=str, help='Expiry date (YYYY-MM-DD or "Jan 23")')
    args = parser.parse_args()
    
    # Determine mode
    if args.live:
        simulation = False
        print("\n" + "="*60)
        print("  ⚠️  LIVE TRADING MODE - REAL ORDERS WILL BE PLACED!")
        print("="*60)
        confirm = input("  Type 'YES' to confirm: ").strip()
        if confirm != 'YES':
            print("  Cancelled. Use --simulation for paper trading.")
            return
    else:
        simulation = True
        print("\n  Running in SIMULATION mode (no real orders)")
    
    # Test connection only
    if args.test:
        print("\n" + "="*60)
        print("  TESTING KITE CONNECTION")
        print("="*60)
        
        from kiteconnect import KiteConnect
        from config import KITE_API_KEY, KITE_ACCESS_TOKEN
        
        try:
            kite = KiteConnect(api_key=KITE_API_KEY)
            kite.set_access_token(KITE_ACCESS_TOKEN)
            
            # Test profile
            profile = kite.profile()
            print(f"\n  ✅ Connected Successfully!")
            print(f"  User: {profile['user_name']} ({profile['user_id']})")
            print(f"  Email: {profile['email']}")
            
            # Test margins
            margins = kite.margins(segment="equity")
            balance = margins['available']['live_balance']
            print(f"  Balance: ₹{balance:,.2f}")
            
            # Test NIFTY price
            quote = kite.ltp(["NSE:NIFTY 50"])
            nifty = quote["NSE:NIFTY 50"]["last_price"]
            print(f"  NIFTY 50: ₹{nifty:,.2f}")
            
            print("\n  ✅ All tests passed! Ready for trading.")
            print("="*60)
            
        except Exception as e:
            print(f"\n  ❌ Connection Failed: {e}")
            print("\n  Please check:")
            print("  1. Your .env file has valid KITE_API_KEY")
            print("  2. Your access token is fresh (expires daily at 6 AM)")
            print("  3. Run: python3 auth_helper.py to regenerate token")
            print("="*60)
        return
    
    # Run trader
    trader = IntegratedNiftyCETrader(simulation=simulation)
    trader.run(expiry_date=args.expiry)


if __name__ == "__main__":
    main()
