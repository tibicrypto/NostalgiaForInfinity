#!/bin/bash

# Download historical data for top 10 coins (last 60 days)
echo "Downloading data for top 10 coins..."
freqtrade download-data \
  --exchange binance \
  --trading-mode futures \
  --config user_data/private_config.json \
  --pairs BTC/USDT:USDT ETH/USDT:USDT BNB/USDT:USDT XRP/USDT:USDT SOL/USDT:USDT DOGE/USDT:USDT ADA/USDT:USDT TRX/USDT:USDT AVAX/USDT:USDT LINK/USDT:USDT \
  --timeframes 5m 1h 15m 4h 1d \
  --timerange 20250101-20250530

echo "Data download completed!"
echo ""
echo "Starting hyperopt with 200 epochs..."

# Run hyperopt with 200 epochs
freqtrade hyperopt \
  --hyperopt-loss SharpeHyperOptLoss \
  --strategy NostalgiaForInfinityX7 \
  --config user_data/private_config.json \
  --config configs/pairlist-hyperopt-static-binance-futures-usdt.json \
  --timerange 20250101-20250530 \
  --epochs 200 \
  --spaces roi stoploss sell opt_9201 \
  --random-state 42 \
  -j 3

echo ""
echo "Hyperopt completed!"
