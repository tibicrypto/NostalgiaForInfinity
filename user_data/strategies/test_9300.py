import logging
import numpy as np
import talib.abstract as ta
import pandas as pd
import pandas_ta as pta
from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import merge_informative_pair, IntParameter, DecimalParameter, CategoricalParameter
from pandas import DataFrame
from functools import reduce
from freqtrade.persistence import Trade
from datetime import datetime
from typing import Optional
import warnings

log = logging.getLogger(__name__)
warnings.simplefilter(action="ignore", category=pd.errors.PerformanceWarning)

#############################################################################################################
##                 Test_9300 - Scalping Breakout Đồng Pha Strategy                                       ##
##            Multi-timeframe Bollinger Band Squeeze Breakout Strategy                                   ##
##            H1 trend + 15m squeeze + 5m breakout confirmation                                           ##
##                                                                                                         ##
##    Strategy for Freqtrade https://github.com/freqtrade/freqtrade                                        ##
##                                                                                                         ##
#############################################################################################################


class Test9300(IStrategy):
  INTERFACE_VERSION = 3

  def version(self) -> str:
    return "v1.0.0-test9300"

  # Stoploss - calculated dynamically based on ATR
  stoploss = -0.15  # Fallback stoploss
  can_short = True
  
  # Trailing stoploss
  trailing_stop = False
  trailing_only_offset_is_reached = False
  trailing_stop_positive = 0.01
  trailing_stop_positive_offset = 0.02

  use_custom_stoploss = True
  stoploss_on_exchange = False

  # Optimal timeframe for the strategy
  timeframe = "5m"
  info_timeframes = ["15m", "1h"]

  # Run "populate_indicators()" only for new candle
  process_only_new_candles = True

  # These values can be overridden in the config
  use_exit_signal = True
  exit_profit_only = False
  ignore_roi_if_entry_signal = False

  # Number of candles the strategy requires before producing valid signals
  startup_candle_count: int = 200

  # ROI table - Using RR ratio
  minimal_roi = {
    "0": 0.015,  # 1.5% (will be overridden by custom exit)
  }

  # ============ HYPEROPT PARAMETERS ============
  
  # H1 Trend Parameters - Long
  h1_ema_period_long = IntParameter(30, 100, default=50, space="buy", optimize=True)
  h1_rsi_period_long = IntParameter(10, 20, default=14, space="buy", optimize=True)
  h1_rsi_level_long = IntParameter(45, 60, default=50, space="buy", optimize=True)
  
  # H1 Trend Parameters - Short
  h1_ema_period_short = IntParameter(30, 100, default=50, space="sell", optimize=True)
  h1_rsi_period_short = IntParameter(10, 20, default=14, space="sell", optimize=True)
  h1_rsi_level_short = IntParameter(40, 55, default=50, space="sell", optimize=True)
  
  # 15m Squeeze Parameters - Long
  m15_bb_period_long = IntParameter(15, 30, default=20, space="buy", optimize=True)
  m15_bb_std_long = DecimalParameter(1.5, 2.5, default=2.0, decimals=1, space="buy", optimize=True)
  m15_bbw_lookback_long = IntParameter(50, 150, default=100, space="buy", optimize=True)
  m15_bbw_percentile_long = IntParameter(5, 20, default=10, space="buy", optimize=True)
  m15_vol_ma_period_long = IntParameter(30, 70, default=50, space="buy", optimize=True)
  
  # 15m Squeeze Parameters - Short
  m15_bb_period_short = IntParameter(15, 30, default=20, space="sell", optimize=True)
  m15_bb_std_short = DecimalParameter(1.5, 2.5, default=2.0, decimals=1, space="sell", optimize=True)
  m15_bbw_lookback_short = IntParameter(50, 150, default=100, space="sell", optimize=True)
  m15_bbw_percentile_short = IntParameter(5, 20, default=10, space="sell", optimize=True)
  m15_vol_ma_period_short = IntParameter(30, 70, default=50, space="sell", optimize=True)
  
  # 5m Breakout Parameters - Long
  m5_bb_period_long = IntParameter(15, 30, default=20, space="buy", optimize=True)
  m5_bb_std_long = DecimalParameter(1.5, 2.5, default=2.0, decimals=1, space="buy", optimize=True)
  m5_rsi_period_long = IntParameter(10, 20, default=14, space="buy", optimize=True)
  m5_rsi_trigger_long = IntParameter(50, 65, default=55, space="buy", optimize=True)
  m5_vol_ma_period_long = IntParameter(30, 70, default=50, space="buy", optimize=True)
  m5_vol_spike_multiplier_long = DecimalParameter(1.5, 3.0, default=2.0, decimals=1, space="buy", optimize=True)
  
  # 5m Breakout Parameters - Short
  m5_bb_period_short = IntParameter(15, 30, default=20, space="sell", optimize=True)
  m5_bb_std_short = DecimalParameter(1.5, 2.5, default=2.0, decimals=1, space="sell", optimize=True)
  m5_rsi_period_short = IntParameter(10, 20, default=14, space="sell", optimize=True)
  m5_rsi_trigger_short = IntParameter(35, 50, default=45, space="sell", optimize=True)
  m5_vol_ma_period_short = IntParameter(30, 70, default=50, space="sell", optimize=True)
  m5_vol_spike_multiplier_short = DecimalParameter(1.5, 3.0, default=2.0, decimals=1, space="sell", optimize=True)
  
  # Risk Management Parameters - Long
  sl_atr_period_long = IntParameter(10, 20, default=14, space="sell", optimize=True)
  sl_atr_multiplier_long = DecimalParameter(1.0, 2.5, default=1.5, decimals=1, space="sell", optimize=True)
  rr_ratio_long = DecimalParameter(1.0, 2.5, default=1.5, decimals=1, space="sell", optimize=True)
  
  # Risk Management Parameters - Short
  sl_atr_period_short = IntParameter(10, 20, default=14, space="sell", optimize=True)
  sl_atr_multiplier_short = DecimalParameter(1.0, 2.5, default=1.5, decimals=1, space="sell", optimize=True)
  rr_ratio_short = DecimalParameter(1.0, 2.5, default=1.5, decimals=1, space="sell", optimize=True)

  # Enable/disable signals
  long_condition_9300_enable = CategoricalParameter([True, False], default=True, space="buy", optimize=False)
  short_condition_9300_enable = CategoricalParameter([True, False], default=True, space="buy", optimize=False)

  def __init__(self, config: dict) -> None:
    super().__init__(config)

  def informative_15m_indicators(self, metadata: dict, df: DataFrame) -> DataFrame:
    """Informative 15m Timeframe Indicators"""
    # Bollinger Bands - Long
    bollinger_long = pta.bbands(df["close"], length=self.m15_bb_period_long.value, std=self.m15_bb_std_long.value)
    df["bb_upper_15m_long"] = bollinger_long[f"BBU_{self.m15_bb_period_long.value}_{self.m15_bb_std_long.value}"]
    df["bb_middle_15m_long"] = bollinger_long[f"BBM_{self.m15_bb_period_long.value}_{self.m15_bb_std_long.value}"]
    df["bb_lower_15m_long"] = bollinger_long[f"BBL_{self.m15_bb_period_long.value}_{self.m15_bb_std_long.value}"]
    df["bbw_15m_long"] = (df["bb_upper_15m_long"] - df["bb_lower_15m_long"]) / df["bb_middle_15m_long"]
    df["bbw_min_hist_15m_long"] = df["bbw_15m_long"].rolling(window=self.m15_bbw_lookback_long.value).apply(
      lambda x: np.percentile(x, self.m15_bbw_percentile_long.value), raw=True
    )
    df["volume_ma_15m_long"] = df["volume"].rolling(window=self.m15_vol_ma_period_long.value).mean()
    
    # Bollinger Bands - Short
    bollinger_short = pta.bbands(df["close"], length=self.m15_bb_period_short.value, std=self.m15_bb_std_short.value)
    df["bb_upper_15m_short"] = bollinger_short[f"BBU_{self.m15_bb_period_short.value}_{self.m15_bb_std_short.value}"]
    df["bb_middle_15m_short"] = bollinger_short[f"BBM_{self.m15_bb_period_short.value}_{self.m15_bb_std_short.value}"]
    df["bb_lower_15m_short"] = bollinger_short[f"BBL_{self.m15_bb_period_short.value}_{self.m15_bb_std_short.value}"]
    df["bbw_15m_short"] = (df["bb_upper_15m_short"] - df["bb_lower_15m_short"]) / df["bb_middle_15m_short"]
    df["bbw_min_hist_15m_short"] = df["bbw_15m_short"].rolling(window=self.m15_bbw_lookback_short.value).apply(
      lambda x: np.percentile(x, self.m15_bbw_percentile_short.value), raw=True
    )
    df["volume_ma_15m_short"] = df["volume"].rolling(window=self.m15_vol_ma_period_short.value).mean()
    
    return df

  def informative_1h_indicators(self, metadata: dict, df: DataFrame) -> DataFrame:
    """Informative 1h Timeframe Indicators"""
    # EMA for trend - Long
    df["ema_1h_long"] = pta.ema(df["close"], length=self.h1_ema_period_long.value)
    df["rsi_1h_long"] = pta.rsi(df["close"], length=self.h1_rsi_period_long.value)
    
    # EMA for trend - Short
    df["ema_1h_short"] = pta.ema(df["close"], length=self.h1_ema_period_short.value)
    df["rsi_1h_short"] = pta.rsi(df["close"], length=self.h1_rsi_period_short.value)
    
    return df

  def base_tf_5m_indicators(self, metadata: dict, df: DataFrame) -> DataFrame:
    """Base timeframe (5m) indicators"""
    # Bollinger Bands - Long
    bollinger_long = pta.bbands(df["close"], length=self.m5_bb_period_long.value, std=self.m5_bb_std_long.value)
    df["bb_upper_long"] = bollinger_long[f"BBU_{self.m5_bb_period_long.value}_{self.m5_bb_std_long.value}"]
    df["bb_middle_long"] = bollinger_long[f"BBM_{self.m5_bb_period_long.value}_{self.m5_bb_std_long.value}"]
    df["bb_lower_long"] = bollinger_long[f"BBL_{self.m5_bb_period_long.value}_{self.m5_bb_std_long.value}"]
    df["rsi_long"] = pta.rsi(df["close"], length=self.m5_rsi_period_long.value)
    df["volume_ma_long"] = df["volume"].rolling(window=self.m5_vol_ma_period_long.value).mean()
    df["atr_long"] = pta.atr(df["high"], df["low"], df["close"], length=self.sl_atr_period_long.value)
    df["prev_close"] = df["close"].shift(1)
    df["prev_bb_upper_long"] = df["bb_upper_long"].shift(1)
    
    # Bollinger Bands - Short
    bollinger_short = pta.bbands(df["close"], length=self.m5_bb_period_short.value, std=self.m5_bb_std_short.value)
    df["bb_upper_short"] = bollinger_short[f"BBU_{self.m5_bb_period_short.value}_{self.m5_bb_std_short.value}"]
    df["bb_middle_short"] = bollinger_short[f"BBM_{self.m5_bb_period_short.value}_{self.m5_bb_std_short.value}"]
    df["bb_lower_short"] = bollinger_short[f"BBL_{self.m5_bb_period_short.value}_{self.m5_bb_std_short.value}"]
    df["rsi_short"] = pta.rsi(df["close"], length=self.m5_rsi_period_short.value)
    df["volume_ma_short"] = df["volume"].rolling(window=self.m5_vol_ma_period_short.value).mean()
    df["atr_short"] = pta.atr(df["high"], df["low"], df["close"], length=self.sl_atr_period_short.value)
    df["prev_bb_lower_short"] = df["bb_lower_short"].shift(1)
    
    return df

  def populate_indicators(self, df: DataFrame, metadata: dict) -> DataFrame:
    """Populate indicators"""
    # Informative 1h
    informative_1h = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe="1h")
    informative_1h = self.informative_1h_indicators(metadata, informative_1h)
    df = merge_informative_pair(df, informative_1h, self.timeframe, "1h", ffill=True)
    
    # Informative 15m
    informative_15m = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe="15m")
    informative_15m = self.informative_15m_indicators(metadata, informative_15m)
    df = merge_informative_pair(df, informative_15m, self.timeframe, "15m", ffill=True)
    
    # Drop duplicate columns
    drop_columns = [f"{s}_1h" for s in ["date", "open", "high", "low", "close", "volume"]]
    drop_columns += [f"{s}_15m" for s in ["date", "open", "high", "low", "close", "volume"]]
    df.drop(columns=df.columns.intersection(drop_columns), inplace=True)
    
    # Base timeframe (5m)
    df = self.base_tf_5m_indicators(metadata, df)
    
    return df

  def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
    """Populate entry signals"""
    df.loc[:, "enter_long"] = 0
    df.loc[:, "enter_short"] = 0
    df.loc[:, "enter_tag"] = ""

    # ============== LONG ENTRY LOGIC ==============
    if self.long_condition_9300_enable.value:
      long_conditions = []
      
      # STEP 1: H1 UPTREND
      long_conditions.append(df["close"] > df["ema_1h_long"])
      long_conditions.append(df["rsi_1h_long"] > self.h1_rsi_level_long.value)
      
      # STEP 2: 15M SQUEEZE
      long_conditions.append(df["bbw_15m_long"] <= df["bbw_min_hist_15m_long"])  # Squeeze condition
      long_conditions.append(df["volume_15m"] < df["volume_ma_15m_long"])  # Low volume
      
      # STEP 3: 5M BREAKOUT
      # Breakout: Previous close was below BB upper, current close is above
      long_conditions.append(df["prev_close"] < df["prev_bb_upper_long"])
      long_conditions.append(df["close"] > df["bb_upper_long"])
      
      # Volume spike
      long_conditions.append(df["volume"] > (df["volume_ma_long"] * self.m5_vol_spike_multiplier_long.value))
      
      # Momentum confirmation
      long_conditions.append(df["rsi_long"] > self.m5_rsi_trigger_long.value)
      
      # Combine all conditions
      if long_conditions:
        df.loc[reduce(lambda x, y: x & y, long_conditions), "enter_long"] = 1
        df.loc[reduce(lambda x, y: x & y, long_conditions), "enter_tag"] = "9300_long_breakout"

    # ============== SHORT ENTRY LOGIC ==============
    if self.short_condition_9300_enable.value:
      short_conditions = []
      
      # STEP 1: H1 DOWNTREND
      short_conditions.append(df["close"] < df["ema_1h_short"])
      short_conditions.append(df["rsi_1h_short"] < self.h1_rsi_level_short.value)
      
      # STEP 2: 15M SQUEEZE
      short_conditions.append(df["bbw_15m_short"] <= df["bbw_min_hist_15m_short"])  # Squeeze condition
      short_conditions.append(df["volume_15m"] < df["volume_ma_15m_short"])  # Low volume
      
      # STEP 3: 5M BREAKDOWN
      # Breakdown: Previous close was above BB lower, current close is below
      short_conditions.append(df["prev_close"] > df["prev_bb_lower_short"])
      short_conditions.append(df["close"] < df["bb_lower_short"])
      
      # Volume spike
      short_conditions.append(df["volume"] > (df["volume_ma_short"] * self.m5_vol_spike_multiplier_short.value))
      
      # Momentum confirmation
      short_conditions.append(df["rsi_short"] < self.m5_rsi_trigger_short.value)
      
      # Combine all conditions
      if short_conditions:
        df.loc[reduce(lambda x, y: x & y, short_conditions), "enter_short"] = 1
        df.loc[reduce(lambda x, y: x & y, short_conditions), "enter_tag"] = "9300_short_breakdown"

    return df

  def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
    """Populate exit signals - handled by custom_exit and custom_stoploss"""
    df.loc[:, "exit_long"] = 0
    df.loc[:, "exit_short"] = 0
    df.loc[:, "exit_tag"] = ""
    return df

  def custom_stoploss(
    self,
    pair: str,
    trade: Trade,
    current_time: datetime,
    current_rate: float,
    current_profit: float,
    **kwargs,
  ) -> float:
    """
    Dynamic stop loss based on ATR
    Returns: stop loss value, relative to current_rate
    """
    try:
      df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    except Exception:
      return self.stoploss

    if len(df) < 5:
      return self.stoploss

    last_candle = df.iloc[-1].squeeze()
    is_short = trade.is_short if hasattr(trade, 'is_short') else False
    
    # Calculate SL based on ATR with direction-specific parameters
    if is_short:
      atr = last_candle.get("atr_short", 0)
      sl_multiplier = self.sl_atr_multiplier_short.value
    else:
      atr = last_candle.get("atr_long", 0)
      sl_multiplier = self.sl_atr_multiplier_long.value
    
    if atr > 0:
      sl_distance = atr * sl_multiplier
      sl_percentage = sl_distance / current_rate
      
      # Return negative value for stop loss
      if is_short:
        return sl_percentage  # For shorts, positive means stop above entry
      else:
        return -sl_percentage  # For longs, negative means stop below entry
    
    return self.stoploss

  def custom_exit(
    self,
    pair: str,
    trade: Trade,
    current_time: datetime,
    current_rate: float,
    current_profit: float,
    **kwargs,
  ) -> Optional[str]:
    """
    Custom exit logic based on Risk:Reward ratio
    """
    try:
      df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    except Exception:
      return None
      
    if len(df) < 5:
      return None

    last_candle = df.iloc[-1].squeeze()
    is_short = trade.is_short if hasattr(trade, 'is_short') else False
    
    # Calculate target profit based on RR ratio with direction-specific parameters
    if is_short:
      atr = last_candle.get("atr_short", 0)
      sl_multiplier = self.sl_atr_multiplier_short.value
      rr_ratio = self.rr_ratio_short.value
    else:
      atr = last_candle.get("atr_long", 0)
      sl_multiplier = self.sl_atr_multiplier_long.value
      rr_ratio = self.rr_ratio_long.value
    
    if atr > 0:
      sl_distance = atr * sl_multiplier
      sl_percentage = sl_distance / trade.open_rate
      
      # Target profit = SL distance * RR ratio
      target_profit = sl_percentage * rr_ratio
      
      # Exit at target
      if current_profit is not None:
        if current_profit >= target_profit:
          return "exit_profit_target_rr"
    
    # Exit on reverse squeeze (price moving back into BB)
    if not is_short:
      # Long position
      if last_candle.get("close", 0) < last_candle.get("bb_middle_long", 0):
        if current_profit is not None and current_profit > 0:
          return "exit_long_bb_middle"
      
      # Exit on momentum loss
      if last_candle.get("rsi_long", 50) < 40:
        return "exit_long_momentum_loss"
      
      # Exit on H1 trend reversal
      if last_candle.get("close", 0) < last_candle.get("ema_1h_long", 0):
        if current_profit is not None and current_profit < 0:
          return "exit_long_h1_reversal"
    
    else:
      # Short position
      if last_candle.get("close", 0) > last_candle.get("bb_middle_short", 0):
        if current_profit is not None and current_profit > 0:
          return "exit_short_bb_middle"
      
      # Exit on momentum loss
      if last_candle.get("rsi_short", 50) > 60:
        return "exit_short_momentum_loss"
      
      # Exit on H1 trend reversal
      if last_candle.get("close", 0) > last_candle.get("ema_1h_short", 0):
        if current_profit is not None and current_profit < 0:
          return "exit_short_h1_reversal"
    
    return None
