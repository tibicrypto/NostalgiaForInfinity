#!/bin/bash

# Activate virtual environment
source .venv/bin/activate

# Configuration
STRATEGY="Test9201"
CONFIG1="user_data/private_config.json"
CONFIG2="configs/pairlist-hyperopt-static-binance-futures-usdt.json"
TIMERANGE="20240101-20251101"
TIMEFRAMES="5m 1h 15m 4h 1d"

# Menu for user selection
echo "========================================="
echo "  Test9201 Strategy - Trading Tools"
echo "========================================="
echo ""
echo "Select an option:"
echo "  1) Download data only"
echo "  2) Run hyperopt (200 epochs)"
echo "  3) Run backtest"
echo "  4) Download data + hyperopt"
echo "  5) Download data + backtest"
echo ""
read -p "Enter your choice [1-5]: " choice

# Function to download data
download_data() {
  echo ""
  echo "Downloading data for top 10 coins..."
  freqtrade download-data \
    --exchange binance \
    --trading-mode futures \
    --config "$CONFIG1" \
    --config "$CONFIG2" \
    --timeframes $TIMEFRAMES \
    --timerange "$TIMERANGE" \
    --prepend
  echo "Data download completed!"
}

# Function to run hyperopt
run_hyperopt() {
  echo ""
  echo "Starting hyperopt with 200 epochs..."
  freqtrade hyperopt \
    --hyperopt-loss SharpeHyperOptLoss \
    --strategy "$STRATEGY" \
    --config "$CONFIG1" \
    --config "$CONFIG2" \
    --timerange "$TIMERANGE" \
    --epochs 200 \
    --spaces opt_9201 roi stoploss \
    --random-state 42 \
    -j 3
  echo ""
  echo "Hyperopt completed!"
}

# Function to run backtest
run_backtest() {
  echo ""
  echo "Starting backtest..."
  freqtrade backtesting \
    --strategy "$STRATEGY" \
    --config "$CONFIG1" \
    --config "$CONFIG2" \
    --timerange "$TIMERANGE" \
    --breakdown month
  echo ""
  echo "Backtest completed!"
  echo ""
  echo "Results saved to user_data/backtest_results/"
}

# Execute based on user choice
case $choice in
  1)
    download_data
    ;;
  2)
    run_hyperopt
    ;;
  3)
    run_backtest
    ;;
  4)
    download_data
    run_hyperopt
    ;;
  5)
    download_data
    run_backtest
    ;;
  *)
    echo "Invalid choice. Please run the script again and select 1-5."
    exit 1
    ;;
esac

echo ""
echo "Script completed!"
