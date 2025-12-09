#!/bin/bash

# Activate virtual environment
source .venv/bin/activate

# Configuration
STRATEGY="NostalgiaForInfinityX9400"
CONFIG_PAIRLIST="configs/pairlist-hyperopt-static-binance-futures-usdt.json"
TIMERANGE="20250101-20251201"
TIMEFRAMES="5m 1h 15m 4h 1d"

# Menu for user selection
echo "========================================="
echo "  Test9201 Strategy - Trading Tools"
echo "========================================="
echo ""
echo "Select an option:"
echo "  1) Download data only"
echo "  2) Run hyperopt (500 epochs)"
echo "  3) Run backtest"
echo "  4) Download data + hyperopt"
echo "  5) Download data + backtest"
echo "  6) Show backtest results"
echo "  7) Show hyperopt results"
echo ""
read -p "Enter your choice [1-7]: " choice

# Function to download data
download_data() {
  echo ""
  echo "Downloading data for top 10 coins..."
  freqtrade download-data \
    --exchange binance \
    --trading-mode futures \
    --config "$CONFIG_PAIRLIST" \
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
    --config "$CONFIG_PAIRLIST" \
    --timerange "$TIMERANGE" \
    --epochs 500 \
    --spaces buy sell stoploss leverage\
    --random-state 42 \
    -j 2
  echo ""
  echo "Hyperopt completed!"
}

# Function to run backtest
run_backtest() {
  echo ""
  echo "Starting backtest..."
  freqtrade backtesting \
    --strategy "$STRATEGY" \
    --config "$CONFIG_PAIRLIST" \
    --timerange "$TIMERANGE" \
    --breakdown month
  echo ""
  echo "Backtest completed!"
  echo ""
  echo "Results saved to user_data/backtest_results/"
}

# Function to show backtest results
show_backtest_results() {
  echo ""
  echo "========================================="
  echo "  Backtest Results"
  echo "========================================="
  echo ""
  
  BACKTEST_DIR="user_data/backtest_results"
  
  if [ ! -d "$BACKTEST_DIR" ]; then
    echo "Error: Backtest results directory not found!"
    echo "Please run a backtest first (option 3 or 5)."
    return 1
  fi
  
  # Find the most recent backtest result file
  LATEST_RESULT=$(ls -t "$BACKTEST_DIR"/*.json 2>/dev/null | head -1)
  
  if [ -z "$LATEST_RESULT" ]; then
    echo "No backtest results found in $BACKTEST_DIR"
    echo "Please run a backtest first (option 3 or 5)."
    return 1
  fi
  
  echo "Latest backtest result: $(basename "$LATEST_RESULT")"
  echo ""
  
  # Use freqtrade to show the results
  freqtrade backtesting-show
  
  echo ""
  echo "========================================="
}

# Function to show hyperopt results
show_hyperopt_results() {
  echo ""
  echo "========================================="
  echo "  Hyperopt Results"
  echo "========================================="
  echo ""
  
  HYPEROPT_DIR="user_data/hyperopt_results"
  
  if [ ! -d "$HYPEROPT_DIR" ]; then
    echo "Error: Hyperopt results directory not found!"
    echo "Please run hyperopt first (option 2 or 4)."
    return 1
  fi
  
  # Find the most recent hyperopt result file
  LATEST_RESULT=$(ls -t "$HYPEROPT_DIR"/*.pkl 2>/dev/null | head -1)
  
  if [ -z "$LATEST_RESULT" ]; then
    echo "No hyperopt results found in $HYPEROPT_DIR"
    echo "Please run hyperopt first (option 2 or 4)."
    return 1
  fi
  
  echo "Latest hyperopt result: $(basename "$LATEST_RESULT")"
  echo ""
  
  # Show hyperopt results summary
  freqtrade hyperopt-show \
    --best \
    --no-header
  
  echo ""
  echo "========================================="
  echo ""
  echo "To see more detailed results, you can run:"
  echo "  - Show top 5 epochs: freqtrade hyperopt-show -n 5"
  echo "  - Show specific epoch: freqtrade hyperopt-show --best"
  echo "  - Export to CSV: freqtrade hyperopt-show --export-csv results.csv"
  echo ""
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
  6)
    show_backtest_results
    ;;
  7)
    show_hyperopt_results
    ;;
  *)
    echo "Invalid choice. Please run the script again and select 1-7."
    exit 1
    ;;
esac

echo ""
echo "Script completed!"
