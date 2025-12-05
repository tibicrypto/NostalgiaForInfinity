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
##                 Test_9201 - BearRider Short Strategy                                                   ##
##            Extracted from NostalgiaForInfinityX7                                                        ##
##            https://github.com/iterativv/NostalgiaForInfinity                                            ##
##                                                                                                         ##
##    Strategy for Freqtrade https://github.com/freqtrade/freqtrade                                        ##
##                                                                                                         ##
#############################################################################################################


class Test9201(IStrategy):
  INTERFACE_VERSION = 3

  def version(self) -> str:
    return "v1.0.0-test9201"

  # Stoploss - fixed value (not optimized in opt_9201 space)
  stoploss = -0.15

  # Trailing stoploss (not used)
  trailing_stop = False
  trailing_only_offset_is_reached = True
  trailing_stop_positive = 0.01
  trailing_stop_positive_offset = 0.03

  use_custom_stoploss = False
  stoploss_on_exchange = False

  # Optimal timeframe for the strategy
  timeframe = "5m"
  info_timeframes = ["1h"]

  # Backtest Age Filter emulation
  has_bt_agefilter = False
  bt_min_age_days = 3

  # Exchange Downtime protection
  has_downtime_protection = False

  # Do you want to use the hold feature?
  hold_support_enabled = False

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

  # Futures mode settings
  is_futures_mode = False
  futures_mode_leverage = 3.0

  # Short BearRider mode tags
  short_bearrider_mode_tags = ["9201"]
  short_bearrider_mode_name = "short_bearrider"

  # BearRider (9201) configuration and hyperopt parameters
  bearrider_phase2_enable = CategoricalParameter([True, False], default=True, space="sell", optimize=True)

  # Stop thresholds
  stop_threshold_bearrider_spot = 0.15
  stop_threshold_bearrider_futures = 0.35

  # Stake multipliers
  bearrider_mode_stake_multiplier_spot = [0.85]
  bearrider_mode_stake_multiplier_futures = [0.85]

  # Hyperopt parameters for 9201
  short_condition_9201_enable = CategoricalParameter([True, False], default=True, space="opt_9201", optimize=True)
  short_condition_9201_adx_min = IntParameter(20, 35, default=25, space="opt_9201", optimize=True)
  short_condition_9201_adx_max = IntParameter(50, 80, default=70, space="opt_9201", optimize=True)
  short_condition_9201_minus_di_min = IntParameter(20, 35, default=25, space="opt_9201", optimize=True)
  short_condition_9201_mfi_max = IntParameter(30, 50, default=40, space="opt_9201", optimize=True)
  short_condition_9201_rsi_1h_min = IntParameter(15, 30, default=20, space="opt_9201", optimize=True)
  short_condition_9201_rsi_1h_max = IntParameter(45, 60, default=50, space="opt_9201", optimize=True)
  short_condition_9201_volume_factor = DecimalParameter(0.8, 1.5, default=1.0, decimals=1, space="opt_9201", optimize=True)
  short_condition_9201_ema_ribbon_enable = CategoricalParameter([0, 1], default=1, space="opt_9201", optimize=True)
  short_condition_9201_1h_confirmation_enable = CategoricalParameter([0, 1], default=1, space="opt_9201", optimize=True)

  # Phase1 advanced
  short_condition_9201_atr_min = DecimalParameter(0.8, 2.5, default=1.5, decimals=1, space="opt_9201", optimize=True)
  short_condition_9201_bb_width_min = DecimalParameter(2.0, 5.0, default=3.0, decimals=1, space="opt_9201", optimize=True)
  short_condition_9201_adx_slope_enable = CategoricalParameter([0, 1], default=1, space="opt_9201", optimize=True)
  short_condition_9201_supertrend_enable = CategoricalParameter([0, 1], default=1, space="opt_9201", optimize=True)
  short_condition_9201_obv_enable = CategoricalParameter([0, 1], default=1, space="opt_9201", optimize=True)
  short_condition_9201_stochrsi_min = IntParameter(40, 70, default=50, space="opt_9201", optimize=True)
  short_condition_9201_willr_min = IntParameter(-40, -10, default=-20, space="opt_9201", optimize=True)
  short_condition_9201_willr_max = IntParameter(-90, -70, default=-80, space="opt_9201", optimize=True)
  short_condition_9201_vwap_enable = CategoricalParameter([0, 1], default=1, space="opt_9201", optimize=True)
  short_condition_9201_volume_relative_min = DecimalParameter(1.0, 2.0, default=1.2, decimals=1, space="opt_9201", optimize=True)
  short_condition_9201_roc_max = IntParameter(-5, 0, default=-1, space="opt_9201", optimize=True)
  short_condition_9201_cmo_max = IntParameter(-20, -5, default=-10, space="opt_9201", optimize=True)
  bearrider_regime_volatility_threshold = DecimalParameter(0.8, 2.5, default=1.2, decimals=1, space="opt_9201", optimize=True)

  # Hyperopt ROI parameters
  bearrider_roi_0 = DecimalParameter(0.005, 0.20, default=0.03, decimals=3, space="sell", optimize=True)
  bearrider_roi_1 = DecimalParameter(0.001, 0.10, default=0.01, decimals=3, space="sell", optimize=True)
  bearrider_roi_2 = DecimalParameter(0.0005, 0.05, default=0.005, decimals=4, space="sell", optimize=True)
  bearrider_roi_1_time = IntParameter(5, 240, default=30, space="opt_9201", optimize=True)
  bearrider_roi_2_time = IntParameter(60, 1440, default=1440, space="opt_9201", optimize=True)

  def minimal_roi(self) -> dict:
    """Construct minimal ROI schedule from hyperopt parameters."""
    try:
      return {
        0: float(self.bearrider_roi_0.value),
        int(self.bearrider_roi_1_time.value): float(self.bearrider_roi_1.value),
        int(self.bearrider_roi_2_time.value): float(self.bearrider_roi_2.value),
      }
    except Exception:
      return {0: 0.03, 30: 0.01, 1440: 0.005}

  # Entry signal params
  short_entry_signal_params = {
    "short_entry_condition_9201_enable": True,
  }

  def __init__(self, config: dict) -> None:
    super().__init__(config)
    if ("trading_mode" in self.config) and (self.config["trading_mode"] in ["futures", "margin"]):
      self.is_futures_mode = True

  def informative_1h_indicators(self, metadata: dict, info_timeframe) -> DataFrame:
    """Informative 1h Timeframe Indicators"""
    assert self.dp, "DataProvider is required for multiple timeframes."
    informative_1h = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe=info_timeframe)

    # RSI
    informative_1h["RSI_14"] = pta.rsi(informative_1h["close"], length=14)
    # EMA
    informative_1h["EMA_200"] = pta.ema(informative_1h["close"], length=200, fillna=0.0)
    # CMF
    informative_1h["CMF_20"] = pta.cmf(
      informative_1h["high"], informative_1h["low"], informative_1h["close"], informative_1h["volume"], length=20
    )

    return informative_1h

  def base_tf_5m_indicators(self, metadata: dict, df: DataFrame) -> DataFrame:
    """Base timeframe (5m) indicators"""
    # RSI
    df["RSI_14"] = pta.rsi(df["close"], length=14)
    # EMA
    df["EMA_8"] = pta.ema(df["close"], length=8)
    df["EMA_21"] = pta.ema(df["close"], length=21)
    df["EMA_200"] = pta.ema(df["close"], length=200, fillna=0.0)
    # MFI
    df["MFI_14"] = pta.mfi(df["high"], df["low"], df["close"], df["volume"], length=14)
    # Williams %R
    df["WILLR_14"] = pta.willr(df["high"], df["low"], df["close"], length=14)
    # Stochastic RSI
    stochrsi = pta.stochrsi(df["close"])
    df["STOCHRSIk_14_14_3_3"] = (
      stochrsi["STOCHRSIk_14_14_3_3"] if isinstance(stochrsi, pd.DataFrame) else np.nan
    )
    df["STOCHRSId_14_14_3_3"] = (
      stochrsi["STOCHRSId_14_14_3_3"] if isinstance(stochrsi, pd.DataFrame) else np.nan
    )
    # OBV
    df["OBV"] = pta.obv(df["close"], df["volume"])
    # ROC
    df["ROC_9"] = pta.roc(df["close"], length=9)
    # Volume
    df["volume_mean_12"] = df["volume"].rolling(window=12, min_periods=1).mean()
    # Number of empty candles
    df["num_empty_288"] = (df["volume"] <= 0).rolling(window=288, min_periods=288).sum()

    # ADX and DI
    adx = pta.adx(df["high"], df["low"], df["close"], length=14)
    if isinstance(adx, pd.DataFrame):
      df["ADX_14"] = adx.get("ADX_14")
      df["PLUS_DI_14"] = adx.get("DMP_14")
      df["MINUS_DI_14"] = adx.get("DMN_14")
    else:
      df["ADX_14"] = np.nan
      df["PLUS_DI_14"] = np.nan
      df["MINUS_DI_14"] = np.nan

    # ATR
    df["ATR_14"] = pta.atr(df["high"], df["low"], df["close"], length=14)
    df["ATR_percent"] = df["ATR_14"] / df["close"] * 100.0

    # Bollinger Bands
    bbands_20_2 = pta.bbands(df["close"], length=20)
    df["BBL_20_2.0"] = bbands_20_2["BBL_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    df["BBM_20_2.0"] = bbands_20_2["BBM_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    df["BBU_20_2.0"] = bbands_20_2["BBU_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    if ("BBU_20_2.0" in df.columns) and ("BBL_20_2.0" in df.columns) and ("BBM_20_2.0" in df.columns):
      df["BB_width_20"] = (df["BBU_20_2.0"] - df["BBL_20_2.0"]) / df["BBM_20_2.0"] * 100.0

    # ADX slope
    df["ADX_slope"] = df["ADX_14"] - df["ADX_14"].shift(3)

    # SuperTrend
    try:
      st10 = pta.supertrend(df["high"], df["low"], df["close"], length=10, multiplier=3.0)
      st11 = pta.supertrend(df["high"], df["low"], df["close"], length=11, multiplier=2.0)
      if isinstance(st10, pd.DataFrame):
        df["ST_10_3"] = st10.iloc[:, -1]
      if isinstance(st11, pd.DataFrame):
        df["ST_11_2"] = st11.iloc[:, -1]
    except Exception:
      df["ST_10_3"] = np.nan
      df["ST_11_2"] = np.nan

    # Parabolic SAR
    try:
      df["SAR"] = ta.SAR(df["high"], df["low"], acceleration=0.02, maximum=0.2)
    except Exception:
      df["SAR"] = np.nan

    # Order flow indicators
    df["OBV_EMA_20"] = pta.ema(df["OBV"], length=20)
    try:
      ad = pta.ad(df["high"], df["low"], df["close"], df["volume"]) if hasattr(pta, "ad") else None
      df["AD"] = ad if isinstance(ad, (pd.Series, pd.DataFrame)) else np.nan
    except Exception:
      df["AD"] = np.nan
    df["AD_slope"] = df["AD"].diff(5)

    # VPT and EOM
    try:
      df["VPT"] = pta.vpt(df["close"], df["volume"]) if hasattr(pta, "vpt") else np.nan
      df["VPT_EMA_20"] = pta.ema(df["VPT"], length=20) if "VPT" in df.columns else np.nan
    except Exception:
      df["VPT"] = np.nan
      df["VPT_EMA_20"] = np.nan

    df["EOM_14"] = pta.eom(df["high"], df["low"], df["close"], df["volume"], length=14) if hasattr(pta, "eom") else np.nan

    # Advanced momentum
    df["MOM_10"] = pta.mom(df["close"], length=10)
    df["CMO_14"] = pta.cmo(df["close"], length=14)

    # VWAP
    try:
      df["VWAP"] = pta.vwap(df["high"], df["low"], df["close"], df["volume"]) if hasattr(pta, "vwap") else np.nan
    except Exception:
      df["VWAP"] = np.nan

    df["VO"] = pta.sma(df["volume"], length=5) - pta.sma(df["volume"], length=10)

    # NVI
    vol = df["volume"].fillna(0)
    pct = df["close"].pct_change().fillna(0)
    mask = vol < vol.shift(1)
    factor = np.where(mask, 1.0 + pct, 1.0)
    factor = pd.Series(factor, index=df.index).fillna(1.0)
    df["NVI"] = 1000.0 * factor.cumprod()
    df["NVI_EMA_255"] = pta.ema(df["NVI"], length=255)

    # PVT
    df["PVT"] = ((df["close"] - df["close"].shift(1)) / df["close"].shift(1)) * df["volume"]
    df["PVT_slope"] = df["PVT"].diff(5)

    # Volume relative
    df["volume_relative"] = df["volume"] / (pta.sma(df["volume"], length=50) + 1e-9)

    # Regime flags
    try:
      df["be_regime_trending"] = (df["ADX_14"] > self.short_condition_9201_adx_min.value) & (
        df["BB_width_20"] > self.bearrider_regime_volatility_threshold.value
      )
      df["be_regime_volatile"] = df["ATR_percent"] > self.bearrider_regime_volatility_threshold.value
    except Exception:
      df["be_regime_trending"] = False
      df["be_regime_volatile"] = False

    # Global protections
    if not self.config["runmode"].value in ("live", "dry_run"):
      df["bt_agefilter_ok"] = False
      df.loc[df.index > (12 * 24 * self.bt_min_age_days), "bt_agefilter_ok"] = True
    else:
      df["live_data_ok"] = df["volume"].rolling(window=72, min_periods=72).min() > 0

    # Simple protections
    df["protections_short_global"] = True
    df["global_protections_short_pump"] = True
    df["global_protections_short_dump"] = True

    return df

  def populate_indicators(self, df: DataFrame, metadata: dict) -> DataFrame:
    """Populate indicators"""
    # Informative 1h
    informative_1h = self.informative_1h_indicators(metadata, "1h")
    df = merge_informative_pair(df, informative_1h, self.timeframe, "1h", ffill=True)
    drop_columns = [f"{s}_1h" for s in ["date", "open", "high", "low", "close", "volume"]]
    df.drop(columns=df.columns.intersection(drop_columns), inplace=True)

    # Base timeframe (5m)
    df = self.base_tf_5m_indicators(metadata, df)

    # Fix NaN values
    df["RSI_14_1h"] = df["RSI_14_1h"].astype(np.float64).fillna(50.0)

    return df

  def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
    """Populate entry signals for BearRider 9201"""
    df.loc[:, "enter_long"] = 0
    df.loc[:, "enter_short"] = 0
    df.loc[:, "enter_tag"] = ""

    short_entry_logic = []
    allowed_empty_candles_288 = 24

    # Only execute if enabled
    if not self.short_condition_9201_enable.value:
      return df

    # Basic protections
    short_entry_logic.append(df["num_empty_288"] <= allowed_empty_candles_288)
    short_entry_logic.append((df["protections_short_global"] == True) | (df["protections_short_global"].isna()))
    short_entry_logic.append((df["global_protections_short_pump"] == True) | (df["global_protections_short_pump"].isna()))
    short_entry_logic.append((df["global_protections_short_dump"] == True) | (df["global_protections_short_dump"].isna()))

    # Phase2 regime requirement (optional)
    if self.bearrider_phase2_enable.value:
      short_entry_logic.append((df.get("be_regime_trending") == True) | (df.get("be_regime_trending").isna()))

    # Layer 1 - Volatility
    short_entry_logic.append(df.get("ATR_percent", 0.0).fillna(0.0) > self.short_condition_9201_atr_min.value)
    short_entry_logic.append(df.get("BB_width_20", 0.0).fillna(0.0) > self.short_condition_9201_bb_width_min.value)

    # Layer 2 - ADX strength
    short_entry_logic.append(
      (df.get("ADX_14", 0.0).fillna(0.0) > self.short_condition_9201_adx_min.value)
      & (df.get("ADX_14", 0.0).fillna(0.0) < self.short_condition_9201_adx_max.value)
    )
    if self.short_condition_9201_adx_slope_enable.value:
      short_entry_logic.append(df.get("ADX_slope", 0.0).fillna(0.0) > 0)

    # Layer 3 - Directional
    short_entry_logic.append(
      df.get("MINUS_DI_14", 0.0).fillna(0.0) > df.get("PLUS_DI_14", 0.0).fillna(0.0)
    )
    short_entry_logic.append(df.get("MINUS_DI_14", 0.0).fillna(0.0) > self.short_condition_9201_minus_di_min.value)

    # Layer 4 - Trend persistence
    if self.short_condition_9201_supertrend_enable.value:
      short_entry_logic.append(df.get("ST_10_3", 0.0).fillna(0.0) < 0)
      short_entry_logic.append(df.get("ST_11_2", 0.0).fillna(0.0) < 0)
    short_entry_logic.append(df.get("close", 0.0) < df.get("SAR", 0.0).fillna(0.0))

    # Layer 5 - Order flow
    if self.short_condition_9201_obv_enable.value:
      short_entry_logic.append(df.get("OBV", 0.0).fillna(0.0) < df.get("OBV_EMA_20", 0.0).fillna(0.0))
      short_entry_logic.append(df.get("AD_slope", 0.0).fillna(0.0) < 0)
      short_entry_logic.append(df.get("VPT", 0.0).fillna(0.0) < df.get("VPT_EMA_20", 0.0).fillna(0.0))
      short_entry_logic.append(df.get("EOM_14", 0.0).fillna(0.0) < 0)

    # Layer 6 - Advanced momentum
    short_entry_logic.append(
      (df.get("STOCHRSIk_14_14_3_3", 0.0).fillna(0.0) > self.short_condition_9201_stochrsi_min.value)
      & (df.get("STOCHRSIk_14_14_3_3", 0.0).fillna(0.0) < df.get("STOCHRSId_14_14_3_3", 100.0).fillna(100.0))
    )
    short_entry_logic.append(
      (df.get("WILLR_14", 0.0).fillna(0.0) > self.short_condition_9201_willr_max.value)
      & (df.get("WILLR_14", 0.0).fillna(0.0) < self.short_condition_9201_willr_min.value)
    )
    short_entry_logic.append(df.get("ROC_9", 0.0).fillna(0.0) < self.short_condition_9201_roc_max.value)
    short_entry_logic.append(df.get("MOM_10", 0.0).fillna(0.0) < 0)
    short_entry_logic.append(df.get("CMO_14", 0.0).fillna(0.0) < self.short_condition_9201_cmo_max.value)

    # Layer 7 - Money flow
    short_entry_logic.append(df.get("MFI_14", 100.0).fillna(100.0) < self.short_condition_9201_mfi_max.value)
    short_entry_logic.append(
      (df.get("RSI_14", 0.0).fillna(0.0) > 25.0) & (df.get("RSI_14", 0.0).fillna(0.0) < 70.0)
    )

    # Layer 8 - EMA ribbon
    if self.short_condition_9201_ema_ribbon_enable.value:
      short_entry_logic.append(
        (df.get("close", 0.0) < df.get("EMA_8", 0.0).fillna(0.0))
        & (df.get("EMA_8", 0.0).fillna(0.0) < df.get("EMA_21", 0.0).fillna(0.0))
      )

    # Layer 9 - Enhanced volume
    if self.short_condition_9201_vwap_enable.value:
      short_entry_logic.append(df.get("close", 0.0) < df.get("VWAP", 0.0).fillna(0.0))
    short_entry_logic.append(df.get("VO", 0.0).fillna(0.0) > 0)
    short_entry_logic.append(df.get("NVI", 0.0).fillna(0.0) < df.get("NVI_EMA_255", 0.0).fillna(0.0))
    short_entry_logic.append(df.get("PVT_slope", 0.0).fillna(0.0) < 0)
    short_entry_logic.append(df.get("volume_relative", 0.0).fillna(0.0) > self.short_condition_9201_volume_relative_min.value)
    short_entry_logic.append(df["volume"] > (df.get("volume_mean_12", 0.0).fillna(0.0) * self.short_condition_9201_volume_factor.value))

    # Layer 10 - 1h confirmation
    if self.short_condition_9201_1h_confirmation_enable.value:
      short_entry_logic.append(df.get("close", 0.0) < df.get("EMA_200_1h", 0.0).fillna(0.0))
      short_entry_logic.append(
        (df.get("RSI_14_1h", 50.0).fillna(50.0) > self.short_condition_9201_rsi_1h_min.value)
        & (df.get("RSI_14_1h", 50.0).fillna(50.0) < self.short_condition_9201_rsi_1h_max.value)
      )
      short_entry_logic.append(df.get("CMF_20_1h", 0.0).fillna(0.0) < 0)

    # Final volume check
    short_entry_logic.append(df["volume"] > 0)

    # Combine all conditions
    item_short_entry = reduce(lambda x, y: x & y, short_entry_logic)
    df.loc[item_short_entry, "enter_tag"] += "9201 "
    df.loc[:, "enter_short"] = item_short_entry

    return df

  def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
    """Populate exit signals - handled by custom_exit"""
    df.loc[:, "exit_long"] = 0
    df.loc[:, "exit_short"] = 0
    df.loc[:, "exit_tag"] = ""
    return df

  def custom_exit(
    self,
    pair: str,
    trade: Trade,
    current_time: datetime,
    current_rate: float,
    current_profit: float,
    **kwargs,
  ) -> Optional[str]:
    """Custom exit logic for BearRider 9201"""
    try:
      df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    except Exception:
      return None
      
    if len(df) < 5:
      return None

    last_candle = df.iloc[-1].squeeze()
    previous_candle_3 = df.iloc[-4].squeeze()

    # Emergency oversold
    if last_candle.get("MFI_14", 100.0) < 10.0:
      return "exit_s9201_mfi_oversold"
    if last_candle.get("RSI_14", 100.0) < 20.0:
      return "exit_s9201_rsi_oversold"
    if last_candle.get("STOCHRSIk_14_14_3_3", 100.0) < 20.0:
      return "exit_s9201_stochrsi_oversold"
    if last_candle.get("WILLR_14", 0.0) < -95.0:
      return "exit_s9201_willr_extreme"

    # Reversal signals
    if last_candle.get("close", 0.0) > last_candle.get("EMA_21", 0.0):
      return "exit_s9201_ema21_break"
    if last_candle.get("PLUS_DI_14", 0.0) > last_candle.get("MINUS_DI_14", 0.0):
      return "exit_s9201_di_reversal"
    if last_candle.get("ST_10_3", 0.0) > 0:
      return "exit_s9201_supertrend_bullish"
    if last_candle.get("close", 0.0) > last_candle.get("VWAP", 0.0):
      return "exit_s9201_vwap_break"

    # Momentum loss
    if last_candle.get("ADX_14", 0.0) < 20.0:
      return "exit_s9201_adx_weak"
    try:
      if (previous_candle_3.get("ADX_14", 0.0) - last_candle.get("ADX_14", 0.0)) > 15.0:
        return "exit_s9201_adx_drop"
    except Exception:
      pass

    # 1h reversal
    if last_candle.get("RSI_14_1h", 0.0) > 60.0:
      return "exit_s9201_rsi_1h_high"
    if last_candle.get("CMF_20_1h", 0.0) > 0.2:
      return "exit_s9201_cmf_1h_high"

    # Tiered profit exits
    if current_profit is not None:
      if 0.005 <= current_profit < 0.02:
        if last_candle.get("OBV", 0.0) > last_candle.get("OBV_EMA_20", 0.0):
          return "exit_s9201_profit_tier1"
      if 0.02 <= current_profit < 0.05:
        if last_candle.get("RSI_14", 0.0) > 60.0 or last_candle.get("EMA_8", 0.0) < last_candle.get("close", 0.0):
          return "exit_s9201_profit_tier2"
      if current_profit >= 0.05:
        if last_candle.get("EMA_8", 0.0) < last_candle.get("close", 0.0):
          return "exit_s9201_profit_tier3"

    return None
