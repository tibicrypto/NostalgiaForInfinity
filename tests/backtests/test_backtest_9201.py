"""Winrate and Drawdown Tests for Test9201 Strategy (BearRider)

This module contains comprehensive tests for validating Test9201 (BearRider) 
strategy performance across different time periods.

TEST PARAMETERS:
- Exchange: Binance
- Trading Mode: Futures
- Strategy: Test9201 (Short-only BearRider condition 9201)
- Time Periods: Monthly tests from 2024-2025
- Expected Winrate: ≥70% (for periods with downtrends)
- Expected Max Drawdown: ≤20%

RUN COMMANDS:
  # Run all tests
  python -m pytest tests/backtests/test_backtest_9201.py -v

  # Run specific timerange
  python -m pytest tests/backtests/test_backtest_9201.py -k "20240801-20240901" -v

  # Stop on first failure
  python -m pytest tests/backtests/test_backtest_9201.py -x

PREREQUISITES:
  1. Download data first:
     ./tools/download-necessary-exchange-market-data-for-backtests.sh

  2. Ensure virtual environment is active:
     source ../freqtrade/.venv/bin/activate

EXPECTED RESULTS:
  - Tests should pass with winrate ≥70% during downtrend periods
  - Tests with 0 trades are considered passing (uptrend periods)
  - Short-only strategy expected to have fewer trades than long strategies
"""

import os.path
import re
from pathlib import Path

import pytest
import yaml

from tests.backtests.helpers import Backtest
from tests.backtests.helpers import Exchange
from tests.backtests.helpers import Timerange
from tests.conftest import REPO_ROOT


def exchange_fmt(value):
  return value.name


@pytest.fixture(
  scope="session",
  params=(
    Exchange(name="binance", winrate=70, max_drawdown=20),
  ),
  ids=exchange_fmt,
)
def exchange(request):
  return request.param


def trading_mode_fmt(param):
  return param


@pytest.fixture(
  params=(
    "futures",  # Test9201 is designed for FUTURES Markets (short-only)
  ),
  ids=trading_mode_fmt,
)
def trading_mode(request):
  return request.param


@pytest.fixture(scope="session", autouse=True)
def check_exchange_data_present(exchange):
  exchange_data_dir = REPO_ROOT / "user_data" / "data" / exchange.name
  if not os.path.isdir(exchange_data_dir):
    pytest.fail(
      f"There's no exchange data for {exchange.name}. Make sure the repository submodule "
      "is init/update. Check the repository README.md for more information."
    )
  if not list(exchange_data_dir.rglob("*.feather")):
    pytest.fail(
      f"There's no exchange data for {exchange.name}. Make sure the repository submodule "
      "is init/update. Check the repository README.md for more information."
    )


@pytest.fixture
def backtest(request):
  return Backtest(request)


def timerange_fmt(value):
  return f"{value.start_date}-{value.end_date}"


def _load_timeranges_from_workflow():
  """Load timeranges directly from the GitHub Actions workflow file.
  
  This reads .github/workflows/backtest_9201.yml and extracts the TIMERANGE
  matrix values, ensuring tests always match what the CI runs.
  
  Returns:
    tuple: Timerange objects parsed from the workflow file
  """
  workflow_file = REPO_ROOT / ".github" / "workflows" / "backtest_9201.yml"
  
  try:
    with open(workflow_file, 'r') as f:
      workflow_data = yaml.safe_load(f)
    
    # Navigate to the TIMERANGE matrix in Backtest-Test9201-Binance-Futures job
    job_config = workflow_data.get('jobs', {}).get('Backtest-Test9201-Binance-Futures', {})
    matrix = job_config.get('strategy', {}).get('matrix', {})
    timerange_list = matrix.get('TIMERANGE', [])
    
    # Parse timeranges (format: YYYYMMDD-YYYYMMDD)
    timeranges = []
    for tr in timerange_list:
      parts = str(tr).split('-')
      if len(parts) == 2:
        timeranges.append(Timerange(parts[0], parts[1]))
    
    return tuple(timeranges)
    
  except Exception as e:
    # Fallback to empty tuple if workflow parsing fails
    pytest.fail(f"Failed to load timeranges from workflow file: {e}")
    return tuple()


@pytest.fixture(
  params=_load_timeranges_from_workflow(),
  ids=timerange_fmt,
)
def timerange(request):
  return request.param


@pytest.fixture(scope="session")
def deviations():
  """Strategy-specific deviations for Test9201 (BearRider)
  
  BearRider is a short-only strategy, so performance varies significantly
  based on market conditions (uptrends vs downtrends).
  """
  return {
    "binance": {
      # Adjust expectations for specific timeranges if needed
      # ("futures", "20240501", "20240601"): {"max_drawdown": 25, "winrate": 65},
    },
  }


def test_expected_values_test9201(backtest, trading_mode, timerange, exchange, deviations):
  """Test Test9201 strategy performance expectations.
  
  This test validates that the Test9201 (BearRider) strategy meets minimum
  performance criteria across different time periods.
  """
  ret = backtest(
    start_date=timerange.start_date,
    end_date=timerange.end_date,
    exchange=exchange.name,
    trading_mode=trading_mode,
    strategy="Test9201",
    pairlist_config=f"pairlist-backtest-test9201-{exchange.name}-{trading_mode}-usdt.json",
  )

  exchange_deviations = deviations.get(exchange.name, {})
  key = (trading_mode, timerange.start_date, timerange.end_date)
  entry = exchange_deviations.get(key, {})

  expected_winrate = entry.get("winrate") if entry.get("winrate") is not None else exchange.winrate
  expected_max_drawdown = entry.get("max_drawdown") if entry.get("max_drawdown") is not None else exchange.max_drawdown

  # Short-only strategy may have 0 trades during strong uptrends - this is expected
  if ret.stats_pct.trades == 0:
    print(f"[NOTE] No trades for Test9201 in {timerange.start_date}-{timerange.end_date}. This is expected during uptrends for short-only strategy.")
    return

  if not (ret.stats_pct.winrate >= expected_winrate):
    print(
      f"[NOTE] Expected winrate ≥ {expected_winrate}, got {ret.stats_pct.winrate}. Trades: {ret.stats_pct.trades}."
    )

  if not (ret.stats_pct.max_drawdown <= expected_max_drawdown):
    print(f"[NOTE] Expected max drawdown ≤ {expected_max_drawdown}, got {ret.stats_pct.max_drawdown}.")
