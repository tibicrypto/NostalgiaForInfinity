import copy
import logging
import pathlib
import rapidjson
import numpy as np
import talib.abstract as ta
import pandas as pd
import pandas_ta as pta
from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import merge_informative_pair, IntParameter, DecimalParameter
from pandas import DataFrame, Series
from functools import reduce
from freqtrade.persistence import Trade, Order
from datetime import datetime, timedelta
import time
from typing import Optional
import warnings

log = logging.getLogger(__name__)
warnings.simplefilter(action="ignore", category=pd.errors.PerformanceWarning)

#############################################################################################################
##                 NostalgiaForInfinityX9400 - Multi-Timeframe Scalping Strategy                         ##
##            Based on NostalgiaForInfinity by iterativ                                                   ##
##            https://github.com/iterativv/NostalgiaForInfinity                                           ##
##                                                                                                         ##
##    Strategy for Freqtrade https://github.com/freqtrade/freqtrade                                        ##
##                                                                                                         ##
##    This strategy focuses on conditions 7 (long) and 907 (short) from X7:                               ##
##    Multi-timeframe scalping with H1 trend, M15 squeeze, M5 breakout confirmation                       ##
##                                                                                                         ##
#############################################################################################################
##               GENERAL RECOMMENDATIONS                                                                   ##
##                                                                                                         ##
##   For optimal performance, suggested to use between 6 and 12 open trades, with unlimited stake.         ##
##   A pairlist with 40 to 80 pairs. Volume pairlist works well.                                           ##
##   Prefer stable coin (USDT, USDC etc) pairs, instead of BTC or ETH pairs.                              ##
##   Highly recommended to blacklist leveraged tokens (*BULL, *BEAR, *UP, *DOWN etc).                      ##
##   Ensure that you don't override any variables in you config.json. Especially                           ##
##   the timeframe (must be 5m).                                                                           ##
##     use_exit_signal must set to true (or not set at all).                                               ##
##     exit_profit_only must set to false (or not set at all).                                             ##
##     ignore_roi_if_entry_signal must set to true (or not set at all).                                    ##
##                                                                                                         ##
#############################################################################################################


class NostalgiaForInfinityX9400(IStrategy):
  INTERFACE_VERSION = 3

  def version(self) -> str:
    return "v1.0.0"

  # Stoploss - hyperopt
  stoploss = -0.15
  
  # Hyperopt parameters for stoploss
  #stoploss_hyperopt = DecimalParameter(-0.30, -0.05, default=-0.15, decimals=3, space="stoploss", optimize=True, load=True)

  # Trailing stoploss (not used)
  trailing_stop = False
  trailing_only_offset_is_reached = True
  trailing_stop_positive = 0.01
  trailing_stop_positive_offset = 0.03

  can_short = True
  use_custom_stoploss = False
  stoploss_on_exchange = False

  # Optimal timeframe for the strategy
  timeframe = "5m"
  info_timeframes = ["15m", "1h"]

  # BTC informatives
  btc_info_timeframes = ["5m", "15m", "1h"]

  # Backtest Age Filter emulation
  has_bt_agefilter = False
  bt_min_age_days = 3

  # Exchange Downtime protection
  has_downtime_protection = False

  # Do you want to use the hold feature? (with hold-trades.json)
  hold_support_enabled = True

  # Run "populate_indicators()" only for new candle
  process_only_new_candles = True

  # These values can be overridden in the "ask_strategy" section in the config
  use_exit_signal = True
  exit_profit_only = False
  ignore_roi_if_entry_signal = True

  # Number of candles the strategy requires before producing valid signals
  startup_candle_count: int = 800

  # Number of cores to use for pandas_ta indicators calculations
  num_cores_indicators_calc = 0

  # Hyperopt parameters for condition 7 (Long Scalp)
  buy_condition_7_rsi_1h_min = IntParameter(50, 60, default=55, space="buy", optimize=True)
  buy_condition_7_rsi_1h_max = IntParameter(75, 85, default=80, space="buy", optimize=True)
  buy_condition_7_scalp_rsi_1h_min = IntParameter(50, 60, default=55, space="buy", optimize=True)
  buy_condition_7_scalp_rsi_1h_max = IntParameter(75, 85, default=80, space="buy", optimize=True)
  buy_condition_7_volume_15m_factor = DecimalParameter(0.5, 1.0, default=0.8, decimals=1, space="buy", optimize=True)
  buy_condition_7_volume_5m_factor = DecimalParameter(1.3, 2.5, default=1.7, decimals=1, space="buy", optimize=True)
  buy_condition_7_rsi_5m_min = IntParameter(50, 60, default=55, space="buy", optimize=True)
  buy_condition_7_rsi_5m_max = IntParameter(70, 80, default=75, space="buy", optimize=True)

  # Hyperopt parameters for condition 907 (Short Scalp)
  short_condition_907_rsi_1h_min = IntParameter(15, 25, default=20, space="sell", optimize=True)
  short_condition_907_rsi_1h_max = IntParameter(40, 50, default=45, space="sell", optimize=True)
  short_condition_907_scalp_rsi_1h_min = IntParameter(15, 25, default=20, space="sell", optimize=True)
  short_condition_907_scalp_rsi_1h_max = IntParameter(40, 50, default=45, space="sell", optimize=True)
  short_condition_907_volume_15m_factor = DecimalParameter(0.5, 1.0, default=0.8, decimals=1, space="sell", optimize=True)
  short_condition_907_volume_5m_factor = DecimalParameter(1.3, 2.5, default=1.7, decimals=1, space="sell", optimize=True)
  short_condition_907_rsi_5m_min = IntParameter(20, 30, default=25, space="sell", optimize=True)
  short_condition_907_rsi_5m_max = IntParameter(40, 50, default=45, space="sell", optimize=True)

  # Hyperopt parameters for leverage
  leverage_hyperopt = IntParameter(1, 10, default=1, space="leverage", optimize=True, load=True)

  # Hyperopt parameters for exit conditions (Long)
  exit_long_profit_target_1 = DecimalParameter(0.01, 0.03, default=0.015, decimals=3, space="buy", optimize=True)
  exit_long_profit_target_2 = DecimalParameter(0.03, 0.06, default=0.04, decimals=3, space="buy", optimize=True)
  exit_long_profit_target_3 = DecimalParameter(0.06, 0.12, default=0.08, decimals=3, space="buy", optimize=True)
  exit_long_rsi_overbought = IntParameter(70, 85, default=78, space="buy", optimize=True)
  exit_long_rsi_under = IntParameter(30, 50, default=40, space="buy", optimize=True)
  
  # Hyperopt parameters for exit conditions (Short)
  exit_short_profit_target_1 = DecimalParameter(0.01, 0.03, default=0.015, decimals=3, space="sell", optimize=True)
  exit_short_profit_target_2 = DecimalParameter(0.03, 0.06, default=0.04, decimals=3, space="sell", optimize=True)
  exit_short_profit_target_3 = DecimalParameter(0.06, 0.12, default=0.08, decimals=3, space="sell", optimize=True)
  exit_short_rsi_oversold = IntParameter(15, 30, default=22, space="sell", optimize=True)
  exit_short_rsi_over = IntParameter(50, 70, default=60, space="sell", optimize=True)

  # Long/Short mode tags
  long_scalp_mode_tags = ["9400_long"]
  short_scalp_mode_tags = ["9400_short"]

  is_futures_mode = False

  # Entry signal configuration
  long_entry_signal_params = {
    "long_entry_condition_9400_enable": True,  # Multi-TF Scalp Strategy
  }

  short_entry_signal_params = {
    "short_entry_condition_9400_enable": True,  # Multi-TF Scalp Strategy
  }

  # Minimal ROI designed for the strategy
  minimal_roi = {
    "0": 0.10,
    "10": 0.05,
    "30": 0.03,
    "60": 0.01,
  }

  # Cache
  hold_trades_cache = None

  #############################################################

  def __init__(self, config: dict) -> None:
    super().__init__(config)
    
    if "trading_mode" in self.config:
      if self.config["trading_mode"] in ("futures", "margin"):
        self.is_futures_mode = True

  #############################################################
  # INDICATOR FUNCTIONS
  #############################################################

  def informative_1h_indicators(self, metadata: dict, info_timeframe) -> DataFrame:
    """
    1h timeframe indicators for trend confirmation
    """
    tik = time.perf_counter()
    assert self.dp, "DataProvider is required for multiple timeframes."
    
    informative_1h = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe=info_timeframe)

    # RSI
    informative_1h["RSI_14"] = pta.rsi(informative_1h["close"], length=14)
    
    # Scalp Strategy Indicators (Condition #9400)
    informative_1h["scalp_ema"] = pta.ema(informative_1h["close"], length=100)
    informative_1h["scalp_rsi"] = pta.rsi(informative_1h["close"], length=14)

    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] informative_1h_indicators took: {tok - tik:0.4f} seconds.")

    return informative_1h

  def informative_15m_indicators(self, metadata: dict, info_timeframe) -> DataFrame:
    """
    15m timeframe indicators for squeeze detection
    """
    tik = time.perf_counter()
    assert self.dp, "DataProvider is required for multiple timeframes."
    
    informative_15m = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe=info_timeframe)

    # Scalp Strategy Indicators (Condition #9400) - 15m
    # Bollinger Bands for squeeze detection
    bbands_15m = pta.bbands(informative_15m["close"], length=20)
    informative_15m["scalp_bb_upper"] = bbands_15m["BBU_20_2.0"] if isinstance(bbands_15m, pd.DataFrame) else np.nan
    informative_15m["scalp_bb_lower"] = bbands_15m["BBL_20_2.0"] if isinstance(bbands_15m, pd.DataFrame) else np.nan
    informative_15m["scalp_bb_mid"] = bbands_15m["BBM_20_2.0"] if isinstance(bbands_15m, pd.DataFrame) else np.nan
    
    # Bollinger Band Width
    informative_15m["scalp_bbw"] = (
      (informative_15m["scalp_bb_upper"] - informative_15m["scalp_bb_lower"]) / informative_15m["scalp_bb_mid"]
    )
    
    # BBW minimum threshold (20th percentile over last 100 candles)
    informative_15m["scalp_bbw_min"] = informative_15m["scalp_bbw"].rolling(window=100).quantile(0.20)
    
    # Volume MA
    informative_15m["scalp_vol_ma"] = pta.sma(informative_15m["volume"], length=20)

    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] informative_15m_indicators took: {tok - tik:0.4f} seconds.")

    return informative_15m

  def base_tf_5m_indicators(self, metadata: dict, df: DataFrame) -> DataFrame:
    """
    5m base timeframe indicators for breakout/breakdown confirmation
    """
    tik = time.perf_counter()

    # RSI
    df["RSI_14"] = pta.rsi(df["close"], length=14)
    
    # Number of empty candles
    df["num_empty_288"] = (df["volume"] <= 0).rolling(window=288, min_periods=288).sum()

    # Scalp Strategy Indicators (Condition #9400) - 5m timeframe
    # Bollinger Bands for breakout detection
    bbands_5m = pta.bbands(df["close"], length=20)
    df["scalp_bb_upper_5m"] = bbands_5m["BBU_20_2.0"] if isinstance(bbands_5m, pd.DataFrame) else np.nan
    df["scalp_bb_lower_5m"] = bbands_5m["BBL_20_2.0"] if isinstance(bbands_5m, pd.DataFrame) else np.nan
    
    # RSI for momentum confirmation
    df["scalp_rsi_5m"] = pta.rsi(df["close"], length=14)
    
    # Volume MA for volume spike detection
    df["scalp_vol_ma_5m"] = pta.sma(df["volume"], length=20)
    
    # ATR for stop loss/take profit calculation
    df["scalp_atr_5m"] = pta.atr(df["high"], df["low"], df["close"], length=14)

    # Simple global protections
    df["protections_long_global"] = True
    df["protections_short_global"] = True
    df["global_protections_short_pump"] = True
    df["global_protections_short_dump"] = True

    # Backtest age filter
    if not self.config["runmode"].value in ("live", "dry_run"):
      df["bt_agefilter_ok"] = False
      df.loc[df.index > (12 * 24 * self.bt_min_age_days), "bt_agefilter_ok"] = True
    else:
      df["bt_agefilter_ok"] = True

    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] base_tf_5m_indicators took: {tok - tik:0.4f} seconds.")

    return df

  def info_switcher(self, metadata: dict, info_timeframe) -> DataFrame:
    """
    Route to appropriate informative timeframe function
    """
    if info_timeframe == "1h":
      return self.informative_1h_indicators(metadata, info_timeframe)
    elif info_timeframe == "15m":
      return self.informative_15m_indicators(metadata, info_timeframe)
    else:
      return DataFrame()

  def populate_indicators(self, df: DataFrame, metadata: dict) -> DataFrame:
    """
    Generate all indicators used by the strategy
    """
    tik = time.perf_counter()

    # BTC informative indicators (simplified - just for structure)
    if self.config["stake_currency"] in ["USDT", "BUSD", "USDC", "DAI", "TUSD", "FDUSD", "PAX", "USD", "EUR", "GBP", "TRY"]:
      if ("trading_mode" in self.config) and (self.config["trading_mode"] in ["futures", "margin"]):
        btc_info_pair = f"BTC/{self.config['stake_currency']}:{self.config['stake_currency']}"
      else:
        btc_info_pair = f"BTC/{self.config['stake_currency']}"
    else:
      if ("trading_mode" in self.config) and (self.config["trading_mode"] in ["futures", "margin"]):
        btc_info_pair = "BTC/USDT:USDT"
      else:
        btc_info_pair = "BTC/USDT"

    # Merge informative timeframes
    for info_timeframe in self.info_timeframes:
      info_indicators = self.info_switcher(metadata, info_timeframe)
      df = merge_informative_pair(df, info_indicators, self.timeframe, info_timeframe, ffill=True)
      
      # Drop OHLCV data to save memory
      drop_columns = {
        "1h": [f"{s}_{info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]],
        "15m": [f"{s}_{info_timeframe}" for s in ["date", "high", "low", "volume"]],
      }.get(info_timeframe, [f"{s}_{info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]])
      df.drop(columns=df.columns.intersection(drop_columns), inplace=True)

    # Base timeframe (5m) indicators
    df = self.base_tf_5m_indicators(metadata, df)

    # Fill NaN values
    df["RSI_14_1h"] = df["RSI_14_1h"].astype(np.float64).replace(to_replace=[np.nan, None], value=(50.0))

    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] populate_indicators took: {tok - tik:0.4f} seconds.")

    return df

  #############################################################
  # ENTRY FUNCTIONS
  #############################################################

  def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
    """
    Populate buy/sell signals for both long and short
    """
    df.loc[:, "enter_tag"] = ""
    df.loc[:, "enter_long"] = 0
    df.loc[:, "enter_short"] = 0

    # Long entry condition 9400
    if self.long_entry_signal_params.get("long_entry_condition_9400_enable", False):
      long_entry_logic = []
      long_entry_logic.append(df["bt_agefilter_ok"])
      
      # Protections
      long_entry_logic.append(df["num_empty_288"] <= 5)
      long_entry_logic.append(df["protections_long_global"] == True)

      # Step 1: H1 Uptrend Confirmation
      long_entry_logic.append(df["RSI_14_1h"] > self.buy_condition_7_rsi_1h_min.value)
      long_entry_logic.append(df["scalp_rsi_1h"] > self.buy_condition_7_scalp_rsi_1h_min.value)
      long_entry_logic.append(df["scalp_rsi_1h"] < self.buy_condition_7_scalp_rsi_1h_max.value)

      # Step 2: M15 Squeeze Detection
      long_entry_logic.append(df["scalp_bbw_15m"] <= df["scalp_bbw_min_15m"])
      long_entry_logic.append(df["volume"] < (df["scalp_vol_ma_15m"] * self.buy_condition_7_volume_15m_factor.value))

      # Step 3: M5 Breakout Confirmation
      long_entry_logic.append(df["close"] > df["scalp_bb_upper_5m"])
      long_entry_logic.append(df["volume"] > (df["scalp_vol_ma_5m"] * self.buy_condition_7_volume_5m_factor.value))

      # Step 4: M5 Momentum Confirmation
      long_entry_logic.append(df["scalp_rsi_5m"] > self.buy_condition_7_rsi_5m_min.value)
      long_entry_logic.append(df["scalp_rsi_5m"] < self.buy_condition_7_rsi_5m_max.value)

      if long_entry_logic:
        df.loc[reduce(lambda x, y: x & y, long_entry_logic), "enter_tag"] += "9400_long "
        df.loc[reduce(lambda x, y: x & y, long_entry_logic), "enter_long"] = 1

    # Short entry condition 9400
    if self.short_entry_signal_params.get("short_entry_condition_9400_enable", False):
      short_entry_logic = []
      short_entry_logic.append(df["bt_agefilter_ok"])
      
      # Protections
      short_entry_logic.append(df["num_empty_288"] <= 5)
      short_entry_logic.append(df["protections_short_global"] == True)
      short_entry_logic.append(df["global_protections_short_pump"] == True)
      short_entry_logic.append(df["global_protections_short_dump"] == True)

      # Step 1: H1 Downtrend Confirmation
      short_entry_logic.append(df["RSI_14_1h"] < self.short_condition_907_rsi_1h_max.value)
      short_entry_logic.append(df["scalp_rsi_1h"] < self.short_condition_907_scalp_rsi_1h_max.value)
      short_entry_logic.append(df["scalp_rsi_1h"] > self.short_condition_907_scalp_rsi_1h_min.value)

      # Step 2: M15 Squeeze Detection
      short_entry_logic.append(df["scalp_bbw_15m"] <= df["scalp_bbw_min_15m"])
      short_entry_logic.append(df["volume"] < (df["scalp_vol_ma_15m"] * self.short_condition_907_volume_15m_factor.value))

      # Step 3: M5 Breakdown Confirmation
      short_entry_logic.append(df["close"] < df["scalp_bb_lower_5m"])
      short_entry_logic.append(df["volume"] > (df["scalp_vol_ma_5m"] * self.short_condition_907_volume_5m_factor.value))

      # Step 4: M5 Momentum Confirmation
      short_entry_logic.append(df["scalp_rsi_5m"] < self.short_condition_907_rsi_5m_max.value)
      short_entry_logic.append(df["scalp_rsi_5m"] > self.short_condition_907_rsi_5m_min.value)

      if short_entry_logic:
        df.loc[reduce(lambda x, y: x & y, short_entry_logic), "enter_tag"] += "9400_short "
        df.loc[reduce(lambda x, y: x & y, short_entry_logic), "enter_short"] = 1

    return df

  #############################################################
  # EXIT FUNCTIONS
  #############################################################

  def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
    """
    Populate exit signals with multiple profit targets and momentum reversal detection
    """
    df.loc[:, "exit_tag"] = ""
    df.loc[:, "exit_long"] = 0
    df.loc[:, "exit_short"] = 0

    # Long exit conditions
    # Exit 1: RSI overbought on 5m (momentum exhaustion)
    long_exit_1 = (
      (df["scalp_rsi_5m"] > self.exit_long_rsi_overbought.value) &
      (df["scalp_rsi_5m"].shift(1) < df["scalp_rsi_5m"]) &  # RSI still rising
      (df["volume"] > df["scalp_vol_ma_5m"] * 1.2)
    )
    df.loc[long_exit_1, "exit_long"] = 1
    df.loc[long_exit_1, "exit_tag"] += "long_rsi_ob "

    # Exit 2: Price below BB middle on 5m (momentum reversal)
    long_exit_2 = (
      (df["close"] < df["scalp_bb_upper_5m"]) &
      (df["close"].shift(1) >= df["scalp_bb_upper_5m"]) &  # Just crossed below
      (df["scalp_rsi_5m"] < self.exit_long_rsi_under.value)
    )
    df.loc[long_exit_2, "exit_long"] = 1
    df.loc[long_exit_2, "exit_tag"] += "long_bb_reversal "

    # Exit 3: 1h trend reversal
    long_exit_3 = (
      (df["scalp_rsi_1h"] < 45) &
      (df["scalp_rsi_5m"] < 35) &
      (df["RSI_14_1h"] < 50)
    )
    df.loc[long_exit_3, "exit_long"] = 1
    df.loc[long_exit_3, "exit_tag"] += "long_trend_reversal "

    # Short exit conditions
    # Exit 1: RSI oversold on 5m (momentum exhaustion)
    short_exit_1 = (
      (df["scalp_rsi_5m"] < self.exit_short_rsi_oversold.value) &
      (df["scalp_rsi_5m"].shift(1) > df["scalp_rsi_5m"]) &  # RSI still falling
      (df["volume"] > df["scalp_vol_ma_5m"] * 1.2)
    )
    df.loc[short_exit_1, "exit_short"] = 1
    df.loc[short_exit_1, "exit_tag"] += "short_rsi_os "

    # Exit 2: Price above BB middle on 5m (momentum reversal)
    short_exit_2 = (
      (df["close"] > df["scalp_bb_lower_5m"]) &
      (df["close"].shift(1) <= df["scalp_bb_lower_5m"]) &  # Just crossed above
      (df["scalp_rsi_5m"] > self.exit_short_rsi_over.value)
    )
    df.loc[short_exit_2, "exit_short"] = 1
    df.loc[short_exit_2, "exit_tag"] += "short_bb_reversal "

    # Exit 3: 1h trend reversal
    short_exit_3 = (
      (df["scalp_rsi_1h"] > 55) &
      (df["scalp_rsi_5m"] > 65) &
      (df["RSI_14_1h"] > 50)
    )
    df.loc[short_exit_3, "exit_short"] = 1
    df.loc[short_exit_3, "exit_tag"] += "short_trend_reversal "

    return df

  #############################################################
  # CUSTOM FUNCTIONS
  #############################################################

  def custom_stake_amount(
    self,
    pair: str,
    current_time: datetime,
    current_rate: float,
    proposed_stake: float,
    min_stake: Optional[float],
    max_stake: float,
    leverage: float,
    entry_tag: Optional[str],
    side: str,
    **kwargs,
  ) -> float:
    """
    Custom stake amount per trade
    """
    return proposed_stake

  def confirm_trade_entry(
    self,
    pair: str,
    order_type: str,
    amount: float,
    rate: float,
    time_in_force: str,
    current_time: datetime,
    entry_tag: Optional[str],
    side: str,
    **kwargs,
  ) -> bool:
    """
    Confirm trade entry
    """
    return True

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
    Custom exit with tiered profit targets
    """
    # Get trade direction
    is_long = trade.is_short == False
    
    if is_long:
      # Long position profit targets
      if current_profit >= self.exit_long_profit_target_3.value:
        return "long_profit_target_3"
      elif current_profit >= self.exit_long_profit_target_2.value:
        # At target 2, check if momentum is weakening
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) > 0:
          last_candle = dataframe.iloc[-1].squeeze()
          if last_candle["scalp_rsi_5m"] > self.exit_long_rsi_overbought.value:
            return "long_profit_target_2_rsi_weak"
      elif current_profit >= self.exit_long_profit_target_1.value:
        # At target 1, check for early reversal signs
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) > 0:
          last_candle = dataframe.iloc[-1].squeeze()
          if last_candle["close"] < last_candle["scalp_bb_upper_5m"]:
            if last_candle["scalp_rsi_5m"] < self.exit_long_rsi_under.value:
              return "long_profit_target_1_reversal"
    else:
      # Short position profit targets
      if current_profit >= self.exit_short_profit_target_3.value:
        return "short_profit_target_3"
      elif current_profit >= self.exit_short_profit_target_2.value:
        # At target 2, check if momentum is weakening
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) > 0:
          last_candle = dataframe.iloc[-1].squeeze()
          if last_candle["scalp_rsi_5m"] < self.exit_short_rsi_oversold.value:
            return "short_profit_target_2_rsi_weak"
      elif current_profit >= self.exit_short_profit_target_1.value:
        # At target 1, check for early reversal signs
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) > 0:
          last_candle = dataframe.iloc[-1].squeeze()
          if last_candle["close"] > last_candle["scalp_bb_lower_5m"]:
            if last_candle["scalp_rsi_5m"] > self.exit_short_rsi_over.value:
              return "short_profit_target_1_reversal"
    
    return None

  def confirm_trade_exit(
    self,
    pair: str,
    trade: Trade,
    order_type: str,
    amount: float,
    rate: float,
    time_in_force: str,
    exit_reason: str,
    current_time: datetime,
    **kwargs,
  ) -> bool:
    """
    Confirm trade exit
    """
    return True

  def leverage(
    self,
    pair: str,
    current_time: datetime,
    current_rate: float,
    proposed_leverage: float,
    max_leverage: float,
    entry_tag: Optional[str],
    side: str,
    **kwargs,
  ) -> float:
    """
    Customize leverage for each new trade
    """
    return min(self.leverage_hyperopt.value, max_leverage)
