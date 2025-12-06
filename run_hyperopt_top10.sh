#!/bin/bash

# Activate virtual environment
source .venv/bin/activate

# Download historical data for top 10 coins (last 60 days)
echo "Downloading data for top 10 coins..."
freqtrade download-data \
  --exchange binance \
  --trading-mode futures \
  --config user_data/private_config.json \
  --config configs/pairlist-hyperopt-static-binance-futures-usdt.json \
  --timeframes 5m 1h 15m 4h 1d \
  --timerange 20241201-20250206 \
  --prepend

echo "Data download completed!"
echo ""
echo "Starting hyperopt with 200 epochs..."

# Run hyperopt with 200 epochs
freqtrade hyperopt \
  --hyperopt-loss SharpeHyperOptLoss \
  --strategy Test9201 \
  --config user_data/private_config.json \
  --config configs/pairlist-hyperopt-static-binance-futures-usdt.json \
  --timerange 20241201-20250206 \
  --epochs 200 \
  --spaces opt_9201 \
  --random-state 42 \
  -j 3

echo ""
echo "Hyperopt completed!"
