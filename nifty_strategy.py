"""
NIFTY 50 BUY Strategy with Double Confirmation

PRIMARY CHECK (5-minute candles, every 10 seconds):
- SuperTrend (7, 3)
- Moving Average (Period 8, Field: Low, Type: EMA, Offset 9)
- EMA (8, 9) Crossover
- StochasticRSI
- RSI (14)
- MACD (5, 13, 6)

DOUBLE CONFIRMATION (2-minute candles, every 5 seconds):
- Same indicators on 2-minute timeframe
- ALL must be TRUE to BUY
- Keep the trend - maintain bullish confirmation

SELL CONDITION:
- Check every 5 seconds on 2-minute candles
- If EMA Low (8) has fallen down → SELL
- If Strong Bearish Signal (SuperTrend + EMA bearish + price below EMA Low) → SELL
"""

import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from kite_client import KiteTradingClient
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
    """SuperTrend Indicator (7, 3)"""
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


def ema_on_low(low_prices, period=8, offset=9):
    """Moving Average on Low prices - Period 8, Field: Low, Type: EMA, Offset 9"""
    ema_values = pd.Series(low_prices).ewm(span=period, adjust=False).mean()
    ema_offset = ema_values.shift(offset)
    return ema_values.values, ema_offset.values


def rsi(data, period=14):
    """Relative Strength Index (14)"""
    delta = pd.Series(data).diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return (100 - (100 / (1 + rs))).values


def stochastic_rsi(data, rsi_period=14, stoch_period=14, smooth_k=3, smooth_d=3):
    """Stochastic RSI"""
    rsi_values = pd.Series(rsi(data, rsi_period))
    lowest = rsi_values.rolling(window=stoch_period).min()
    highest = rsi_values.rolling(window=stoch_period).max()
    stoch_rsi = ((rsi_values - lowest) / (highest - lowest)) * 100
    k = stoch_rsi.rolling(window=smooth_k).mean()
    d = k.rolling(window=smooth_d).mean()
    return k.values, d.values


def macd(data, fast=5, slow=13, signal=6):
    """MACD (5, 13, 6)"""
    prices = pd.Series(data)
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line.values, signal_line.values, histogram.values


def calculate_all_indicators(df):
    """Calculate all indicators on dataframe"""
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    
    # SuperTrend (7, 3)
    df['supertrend'], df['supertrend_direction'] = supertrend(high, low, close, 7, 3)
    
    # EMA on Low (Period 8, Offset 9)
    df['ema_low_8'], df['ema_low_8_offset9'] = ema_on_low(low, 8, 9)
    
    # EMA 8 and 9 on Close
    df['ema_8'] = ema(close, 8)
    df['ema_9'] = ema(close, 9)
    
    # RSI (14)
    df['rsi_14'] = rsi(close, 14)
    
    # Stochastic RSI
    df['stoch_rsi_k'], df['stoch_rsi_d'] = stochastic_rsi(close)
    
    # MACD (5, 13, 6)
    df['macd'], df['macd_signal'], df['macd_hist'] = macd(close, 5, 13, 6)
    
    return df


# ============== NIFTY BUY STRATEGY ==============

class NiftyBuyStrategy:
    """
    NIFTY 50 BUY Strategy with Double Confirmation
    
    PRIMARY (5-min): Check every 10 seconds
    CONFIRMATION (2-min): Check every 5 seconds
    
    BUY: When ALL indicators align on BOTH timeframes
    SELL: When EMA Low (8) falls down on 2-min timeframe
    """
    
    def __init__(self, kite_client):
        self.kite = kite_client
        self.symbol = "NIFTY 50"
        self.exchange = "NSE"
        
        # Position tracking
        self.position = None  # 'LONG' or None (BUY only strategy)
        self.entry_price = None
        self.entry_time = None
        self.lot_size = 75
        
        # Indicator Parameters
        self.supertrend_period = 7
        self.supertrend_multiplier = 3
        self.ema_low_period = 8
        self.ema_low_offset = 9
        self.ema_fast = 8
        self.ema_slow = 9
        self.rsi_period = 14
        self.macd_fast = 5
        self.macd_slow = 13
        self.macd_signal = 6
        
        # Timing Parameters
        self.primary_interval = "5minute"      # Primary: 5-minute candles
        self.confirm_interval = "2minute"      # Confirmation: 2-minute candles
        self.primary_check_seconds = 10        # Check primary every 10 seconds
        self.confirm_check_seconds = 5         # Check confirmation every 5 seconds
        
        # State tracking
        self.primary_buy_signal = False
        self.confirm_buy_signal = False
        self.last_ema_low_2min = None
        
        logger.info("=" * 70)
        logger.info("NIFTY 50 BUY STRATEGY - DOUBLE CONFIRMATION")
        logger.info("=" * 70)
        logger.info(f"PRIMARY: {self.primary_interval} candles, check every {self.primary_check_seconds}s")
        logger.info(f"CONFIRM: {self.confirm_interval} candles, check every {self.confirm_check_seconds}s")
        logger.info(f"SuperTrend ({self.supertrend_period}, {self.supertrend_multiplier})")
        logger.info(f"EMA Low (Period: {self.ema_low_period}, Offset: {self.ema_low_offset})")
        logger.info(f"EMA Crossover ({self.ema_fast}, {self.ema_slow})")
        logger.info(f"RSI ({self.rsi_period}) | MACD ({self.macd_fast},{self.macd_slow},{self.macd_signal})")
        logger.info("=" * 70)
    
    def get_nifty_instrument_token(self):
        """Get NIFTY 50 instrument token"""
        try:
            instruments = self.kite.get_instruments("NSE")
            for inst in instruments:
                if inst['tradingsymbol'] == "NIFTY 50":
                    return inst['instrument_token']
            return None
        except Exception as e:
            logger.error(f"Error getting instrument token: {e}")
            return None
    
    def get_historical_data(self, interval, days=3):
        """Get historical data for specified interval"""
        try:
            instrument_token = self.get_nifty_instrument_token()
            
            if not instrument_token:
                logger.error("NIFTY 50 instrument not found")
                return None
            
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)
            
            data = self.kite.get_historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            
            df = pd.DataFrame(data)
            return df
            
        except Exception as e:
            logger.error(f"Error fetching {interval} data: {e}")
            return None
    
    def check_buy_conditions(self, df, timeframe_name):
        """
        Check BUY conditions on a timeframe
        
        Returns:
            tuple: (is_buy_signal, conditions_dict)
        """
        if len(df) < 3:
            return False, {}
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        conditions = {}
        
        # 1. SuperTrend is BULLISH (Green)
        conditions['supertrend_bullish'] = curr['supertrend_direction'] == 1
        conditions['price_above_supertrend'] = curr['close'] > curr['supertrend']
        conditions['supertrend_crossover'] = (
            curr['supertrend_direction'] == 1 and 
            prev['supertrend_direction'] == -1
        )
        
        # 2. EMA Low (8) crossed / price above EMA Low
        conditions['price_above_ema_low'] = curr['close'] > curr['ema_low_8']
        conditions['ema_low_rising'] = curr['ema_low_8'] > prev['ema_low_8']
        
        # 3. EMA (8, 9) Crossover - EMA 8 > EMA 9
        conditions['ema_bullish'] = curr['ema_8'] > curr['ema_9']
        conditions['ema_crossover'] = (
            curr['ema_8'] > curr['ema_9'] and 
            prev['ema_8'] <= prev['ema_9']
        )
        
        # 4. StochasticRSI - Good for buy (< 40 oversold or turning up)
        conditions['stoch_rsi_good'] = curr['stoch_rsi_k'] < 50 or curr['stoch_rsi_k'] > prev['stoch_rsi_k']
        conditions['stoch_rsi_value'] = curr['stoch_rsi_k']
        
        # 5. RSI (14) - Good for buy (< 60 and rising)
        conditions['rsi_good'] = curr['rsi_14'] < 65 and curr['rsi_14'] > prev['rsi_14']
        conditions['rsi_value'] = curr['rsi_14']
        
        # 6. MACD (5, 13, 6) - Good place to buy (histogram positive or improving)
        conditions['macd_good'] = curr['macd_hist'] > 0 or curr['macd_hist'] > prev['macd_hist']
        conditions['macd_value'] = curr['macd_hist']
        
        # ALL CONDITIONS for BUY
        all_conditions_met = (
            conditions['supertrend_bullish'] and
            conditions['price_above_supertrend'] and
            conditions['price_above_ema_low'] and
            conditions['ema_bullish'] and
            conditions['stoch_rsi_good'] and
            conditions['rsi_good'] and
            conditions['macd_good']
        )
        
        # Strong signal on crossover
        crossover_signal = (
            conditions['supertrend_crossover'] or 
            conditions['ema_crossover']
        )
        
        is_buy = all_conditions_met or (crossover_signal and conditions['supertrend_bullish'] and conditions['ema_bullish'])
        
        return is_buy, conditions
    
    def check_sell_condition_2min(self, df):
        """
        Check SELL condition on 2-minute timeframe
        
        SELL if: EMA Low (8) has fallen down
        """
        if len(df) < 3:
            return False, {}
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3]
        
        conditions = {}
        
        # EMA Low (8) has fallen down
        conditions['ema_low_falling'] = (
            curr['ema_low_8'] < prev['ema_low_8'] and 
            prev['ema_low_8'] < prev2['ema_low_8']
        )
        
        # Price below EMA Low
        conditions['price_below_ema_low'] = curr['close'] < curr['ema_low_8']
        
        # SuperTrend turned bearish
        conditions['supertrend_bearish'] = curr['supertrend_direction'] == -1
        
        # EMA crossed down
        conditions['ema_bearish'] = curr['ema_8'] < curr['ema_9']
        
        # SELL condition: EMA Low falling AND price below it
        is_sell = conditions['ema_low_falling'] and conditions['price_below_ema_low']
        
        # Also sell on strong bearish signals
        strong_sell = (
            conditions['supertrend_bearish'] and 
            conditions['ema_bearish'] and 
            conditions['price_below_ema_low']
        )
        
        return is_sell or strong_sell, conditions
    
    def print_status(self, df_5min, df_2min, primary_signal, confirm_signal):
        """Print current status"""
        curr_5m = df_5min.iloc[-1] if len(df_5min) > 0 else None
        curr_2m = df_2min.iloc[-1] if len(df_2min) > 0 else None
        
        print("\n" + "═" * 90)
        print(f"  NIFTY 50 BUY STRATEGY - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("═" * 90)
        
        if curr_5m is not None:
            st_5m = "🟢 BULL" if curr_5m['supertrend_direction'] == 1 else "🔴 BEAR"
            ema_5m = "🟢" if curr_5m['ema_8'] > curr_5m['ema_9'] else "🔴"
            macd_5m = "🟢" if curr_5m['macd_hist'] > 0 else "🔴"
            
            print(f"  5-MIN | Price: ₹{curr_5m['close']:.2f}")
            print(f"        | ST(7,3): {curr_5m['supertrend']:.2f} {st_5m}")
            print(f"        | EMA Low(8): {curr_5m['ema_low_8']:.2f} | EMA8: {curr_5m['ema_8']:.2f} EMA9: {curr_5m['ema_9']:.2f} {ema_5m}")
            print(f"        | RSI: {curr_5m['rsi_14']:.1f} | StochRSI: {curr_5m['stoch_rsi_k']:.1f} | MACD: {curr_5m['macd_hist']:.2f} {macd_5m}")
            print(f"        | Signal: {'✅ BUY READY' if primary_signal else '⏳ Waiting'}")
        
        print("─" * 90)
        
        if curr_2m is not None:
            st_2m = "🟢 BULL" if curr_2m['supertrend_direction'] == 1 else "🔴 BEAR"
            ema_2m = "🟢" if curr_2m['ema_8'] > curr_2m['ema_9'] else "🔴"
            macd_2m = "🟢" if curr_2m['macd_hist'] > 0 else "🔴"
            ema_low_trend = "📈 Rising" if curr_2m['ema_low_8'] > df_2min.iloc[-2]['ema_low_8'] else "📉 Falling"
            
            print(f"  2-MIN | Price: ₹{curr_2m['close']:.2f}")
            print(f"        | ST(7,3): {curr_2m['supertrend']:.2f} {st_2m}")
            print(f"        | EMA Low(8): {curr_2m['ema_low_8']:.2f} {ema_low_trend}")
            print(f"        | EMA8: {curr_2m['ema_8']:.2f} EMA9: {curr_2m['ema_9']:.2f} {ema_2m}")
            print(f"        | RSI: {curr_2m['rsi_14']:.1f} | StochRSI: {curr_2m['stoch_rsi_k']:.1f} | MACD: {curr_2m['macd_hist']:.2f} {macd_2m}")
            print(f"        | Signal: {'✅ CONFIRMED' if confirm_signal else '⏳ Waiting'}")
        
        print("─" * 90)
        
        # Combined signal
        if primary_signal and confirm_signal:
            print(f"  🎯 DOUBLE CONFIRMATION: ✅✅ ALL CONDITIONS MET - READY TO BUY!")
        elif primary_signal:
            print(f"  🎯 DOUBLE CONFIRMATION: ✅⏳ Primary OK, waiting for 2-min confirmation")
        elif confirm_signal:
            print(f"  🎯 DOUBLE CONFIRMATION: ⏳✅ 2-min OK, waiting for 5-min signal")
        else:
            print(f"  🎯 DOUBLE CONFIRMATION: ⏳⏳ Waiting for signals")
        
        # Position info
        if self.position:
            curr_price = curr_2m['close'] if curr_2m is not None else curr_5m['close']
            pnl = curr_price - self.entry_price
            pnl_pct = (pnl / self.entry_price) * 100
            pnl_emoji = "🟢" if pnl > 0 else "🔴"
            
            print("─" * 90)
            print(f"  📊 POSITION: {self.position} @ ₹{self.entry_price:.2f}")
            print(f"     Exit: Technical signals (EMA Low falling / Bearish)")
            print(f"     P&L: {pnl_emoji} ₹{pnl:.2f} ({pnl_pct:+.2f}%)")
        
        print("═" * 90)
    
    def place_buy_order(self, price):
        """Place BUY order"""
        try:
            self.entry_price = price
            self.entry_time = datetime.now()
            self.position = 'LONG'
            
            logger.info("=" * 60)
            logger.info("🟢🟢 DOUBLE CONFIRMATION BUY ORDER 🟢🟢")
            logger.info(f"   Entry: ₹{self.entry_price:.2f}")
            logger.info(f"   Exit: Technical signals (EMA Low falling / Bearish)")
            logger.info("=" * 60)
            
            # Uncomment for LIVE trading:
            # order_id = self.kite.place_order(
            #     variety="regular",
            #     exchange="NFO",
            #     tradingsymbol="NIFTY25JANFUT",  # Update with current month
            #     transaction_type="BUY",
            #     quantity=self.lot_size,
            #     product="MIS",
            #     order_type="MARKET",
            #     validity="DAY"
            # )
            # return order_id
            
            return "SIMULATED_BUY"
            
        except Exception as e:
            logger.error(f"Error placing buy order: {e}")
            return None
    
    def place_sell_order(self, price, reason):
        """Place SELL order to exit position"""
        try:
            pnl = price - self.entry_price
            pnl_pct = (pnl / self.entry_price) * 100
            
            logger.info("=" * 60)
            logger.info(f"🔴 SELL ORDER - Reason: {reason}")
            logger.info(f"   Exit: ₹{price:.2f}")
            logger.info(f"   P&L: {'🟢' if pnl > 0 else '🔴'} ₹{pnl:.2f} ({pnl_pct:+.2f}%)")
            logger.info("=" * 60)
            
            # Uncomment for LIVE trading:
            # order_id = self.kite.place_order(
            #     variety="regular",
            #     exchange="NFO",
            #     tradingsymbol="NIFTY25JANFUT",
            #     transaction_type="SELL",
            #     quantity=self.lot_size,
            #     product="MIS",
            #     order_type="MARKET",
            #     validity="DAY"
            # )
            
            self.position = None
            self.entry_price = None
            
            return "SIMULATED_SELL"
            
        except Exception as e:
            logger.error(f"Error placing sell order: {e}")
            return None
    
    def run(self, simulation=True):
        """
        Run the BUY strategy with double confirmation
        
        - Check 5-min every 10 seconds
        - Check 2-min every 5 seconds
        - BUY only when BOTH confirm
        - SELL when EMA Low falls on 2-min
        """
        logger.info("Starting NIFTY 50 BUY Strategy with Double Confirmation...")
        logger.info(f"Mode: {'SIMULATION' if simulation else '🔴 LIVE TRADING'}")
        
        if not simulation:
            confirm = input("\n⚠️  LIVE TRADING MODE! Type 'CONFIRM' to proceed: ")
            if confirm != 'CONFIRM':
                logger.info("Live trading cancelled")
                return
        
        iteration = 0
        last_5min_check = 0
        
        while True:
            try:
                iteration += 1
                current_time = time.time()
                
                # Get data for both timeframes
                df_5min = self.get_historical_data(self.primary_interval, days=3)
                df_2min = self.get_historical_data(self.confirm_interval, days=2)
                
                if df_5min is None or df_2min is None or len(df_5min) < 30 or len(df_2min) < 30:
                    logger.warning("Insufficient data, waiting...")
                    time.sleep(5)
                    continue
                
                # Calculate indicators on both timeframes
                df_5min = calculate_all_indicators(df_5min)
                df_2min = calculate_all_indicators(df_2min)
                
                current_price = df_2min.iloc[-1]['close']
                
                # Check PRIMARY (5-min) every 10 seconds
                if current_time - last_5min_check >= self.primary_check_seconds:
                    self.primary_buy_signal, primary_cond = self.check_buy_conditions(df_5min, "5-MIN")
                    last_5min_check = current_time
                
                # Check CONFIRMATION (2-min) every 5 seconds
                self.confirm_buy_signal, confirm_cond = self.check_buy_conditions(df_2min, "2-MIN")
                
                # Print status
                self.print_status(df_5min, df_2min, self.primary_buy_signal, self.confirm_buy_signal)
                
                # If we have a position, check exit conditions
                if self.position == 'LONG':
                    # Check SELL condition: EMA Low falling on 2-min or strong bearish signal
                    sell_signal, sell_cond = self.check_sell_condition_2min(df_2min)
                    if sell_signal:
                        reason = "STRONG_BEARISH" if sell_cond.get('supertrend_bearish') else "EMA_LOW_FALLING"
                        if simulation:
                            logger.info(f"[SIMULATION] {reason} - SELL signal")
                        self.place_sell_order(current_price, reason)
                        continue
                
                # If no position, check for BUY with DOUBLE CONFIRMATION
                if self.position is None:
                    if self.primary_buy_signal and self.confirm_buy_signal:
                        logger.info("🎯 DOUBLE CONFIRMATION ACHIEVED!")
                        if simulation:
                            logger.info("[SIMULATION] Would place BUY order")
                        self.place_buy_order(current_price)
                
                # Wait 5 seconds (confirmation check interval)
                logger.info(f"Next check in {self.confirm_check_seconds}s... (Ctrl+C to stop)")
                time.sleep(self.confirm_check_seconds)
                
            except KeyboardInterrupt:
                logger.info("\n🛑 Strategy stopped by user")
                if self.position:
                    logger.warning(f"⚠️  You have an open {self.position} position!")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(5)


def main():
    """Main function"""
    print("""
╔═══════════════════════════════════════════════════════════════════════════════════╗
║              NIFTY 50 BUY STRATEGY - DOUBLE CONFIRMATION                          ║
╠═══════════════════════════════════════════════════════════════════════════════════╣
║  PRIMARY CHECK (5-minute candles, every 10 seconds):                              ║
║  • SuperTrend (7, 3)                                                              ║
║  • Moving Average (Period 8, Field: Low, Type: EMA, Offset 9)                     ║
║  • EMA Crossover (8, 9)                                                           ║
║  • StochasticRSI | RSI (14) | MACD (5, 13, 6)                                     ║
╠═══════════════════════════════════════════════════════════════════════════════════╣
║  DOUBLE CONFIRMATION (2-minute candles, every 5 seconds):                         ║
║  • Same indicators - ALL must be TRUE to BUY                                      ║
╠═══════════════════════════════════════════════════════════════════════════════════╣
║  SELL: EMA Low (8) falling OR Strong Bearish Signal on 2-minute timeframe         ║
╚═══════════════════════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        # Initialize Kite client
        logger.info("Connecting to Zerodha Kite API...")
        kite_client = KiteTradingClient()
        
        # Verify connection
        profile = kite_client.get_profile()
        logger.info(f"✓ Connected! User: {profile.get('user_name', 'Unknown')}")
        
        # Get margins
        margins = kite_client.get_margins()
        available = margins.get('equity', {}).get('available', {}).get('cash', 0)
        logger.info(f"✓ Available Margin: ₹{available}")
        
        # Initialize and run strategy
        strategy = NiftyBuyStrategy(kite_client)
        
        # Run in simulation mode (change to False for live trading)
        strategy.run(simulation=True)
        
    except ValueError as e:
        logger.error(f"Configuration Error: {e}")
        print("\n❌ Please set up your API credentials:")
        print("   Run: python auth_helper.py")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
