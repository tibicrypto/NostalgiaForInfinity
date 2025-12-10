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
echo "  8) Compare last 3 backtest results"
echo "  9) Compare last 3 hyperopt results"
echo ""
read -p "Enter your choice [1-9]: " choice

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
  
  # Find last 5 backtest result files
  mapfile -t RESULT_FILES < <(ls -t "$BACKTEST_DIR"/*.json 2>/dev/null | head -5)
  
  if [ ${#RESULT_FILES[@]} -eq 0 ]; then
    echo "No backtest results found in $BACKTEST_DIR"
    echo "Please run a backtest first (option 3 or 5)."
    return 1
  fi
  
  echo "Available backtest results:"
  echo ""
  for i in "${!RESULT_FILES[@]}"; do
    FILE_NAME=$(basename "${RESULT_FILES[$i]}")
    FILE_DATE=$(stat -c %y "${RESULT_FILES[$i]}" 2>/dev/null | cut -d' ' -f1,2 | cut -d'.' -f1)
    echo "  $((i+1))) $FILE_NAME"
    echo "      Date: $FILE_DATE"
  done
  
  echo ""
  read -p "Select a result to view [1-${#RESULT_FILES[@]}] or press Enter for latest: " selection
  
  if [ -z "$selection" ]; then
    selection=1
  fi
  
  if ! [[ "$selection" =~ ^[0-9]+$ ]] || [ "$selection" -lt 1 ] || [ "$selection" -gt ${#RESULT_FILES[@]} ]; then
    echo "Invalid selection. Showing latest result."
    selection=1
  fi
  
  SELECTED_FILE="${RESULT_FILES[$((selection-1))]}"
  echo ""
  echo "========================================="
  echo "Showing: $(basename "$SELECTED_FILE")"
  echo "========================================="
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
  
  # Find last 5 hyperopt result files
  mapfile -t RESULT_FILES < <(ls -t "$HYPEROPT_DIR"/*.pkl 2>/dev/null | head -5)
  
  if [ ${#RESULT_FILES[@]} -eq 0 ]; then
    echo "No hyperopt results found in $HYPEROPT_DIR"
    echo "Please run hyperopt first (option 2 or 4)."
    return 1
  fi
  
  echo "Available hyperopt results:"
  echo ""
  for i in "${!RESULT_FILES[@]}"; do
    FILE_NAME=$(basename "${RESULT_FILES[$i]}")
    FILE_DATE=$(stat -c %y "${RESULT_FILES[$i]}" 2>/dev/null | cut -d' ' -f1,2 | cut -d'.' -f1)
    echo "  $((i+1))) $FILE_NAME"
    echo "      Date: $FILE_DATE"
  done
  
  echo ""
  read -p "Select a result to view [1-${#RESULT_FILES[@]}] or press Enter for latest: " selection
  
  if [ -z "$selection" ]; then
    selection=1
  fi
  
  if ! [[ "$selection" =~ ^[0-9]+$ ]] || [ "$selection" -lt 1 ] || [ "$selection" -gt ${#RESULT_FILES[@]} ]; then
    echo "Invalid selection. Showing latest result."
    selection=1
  fi
  
  SELECTED_FILE="${RESULT_FILES[$((selection-1))]}"
  echo ""
  echo "========================================="
  echo "Showing: $(basename "$SELECTED_FILE")"
  echo "========================================="
  echo ""
  
  # Show hyperopt results summary for selected file
  freqtrade hyperopt-show \
    --best \
    --no-header \
    --hyperopt-filename "$(basename "$SELECTED_FILE")"
  
  echo ""
  echo "========================================="
  echo ""
  echo "To see more detailed results, you can run:"
  echo "  - Show top 5 epochs: freqtrade hyperopt-show -n 5 --hyperopt-filename $(basename "$SELECTED_FILE")"
  echo "  - Show all results: freqtrade hyperopt-show --hyperopt-filename $(basename "$SELECTED_FILE")"
  echo "  - Export to CSV: freqtrade hyperopt-show --export-csv results.csv --hyperopt-filename $(basename "$SELECTED_FILE")"
  echo ""
}

# Function to compare backtest results
compare_backtest_results() {
  echo ""
  echo "========================================="
  echo "  Compare Backtest Results"
  echo "========================================="
  echo ""
  
  BACKTEST_DIR="user_data/backtest_results"
  
  if [ ! -d "$BACKTEST_DIR" ]; then
    echo "Error: Backtest results directory not found!"
    echo "Please run a backtest first (option 3 or 5)."
    return 1
  fi
  
  # Find last 3 backtest meta files
  mapfile -t RESULT_FILES < <(ls -t "$BACKTEST_DIR"/*.meta.json 2>/dev/null | head -3)
  
  if [ ${#RESULT_FILES[@]} -eq 0 ]; then
    echo "No backtest results found in $BACKTEST_DIR"
    echo "Please run a backtest first (option 3 or 5)."
    return 1
  fi
  
  if [ ${#RESULT_FILES[@]} -lt 2 ]; then
    echo "Not enough backtest results to compare (found ${#RESULT_FILES[@]}, need at least 2)."
    echo "Please run more backtests first."
    return 1
  fi
  
  echo "Comparing the last ${#RESULT_FILES[@]} backtest results:"
  echo ""
  for i in "${!RESULT_FILES[@]}"; do
    FILE_NAME=$(basename "${RESULT_FILES[$i]}" .meta.json)
    FILE_DATE=$(stat -c %y "${RESULT_FILES[$i]}" 2>/dev/null | cut -d' ' -f1,2 | cut -d'.' -f1)
    echo "  $((i+1))) $FILE_NAME"
    echo "      Date: $FILE_DATE"
  done
  
  echo ""
  echo "========================================="
  echo "Detailed Comparison:"
  echo "========================================="
  echo ""
  
  # Show each backtest result using freqtrade
  for i in "${!RESULT_FILES[@]}"; do
    FILE_NAME=$(basename "${RESULT_FILES[$i]}" .meta.json)
    ZIP_FILE="$BACKTEST_DIR/${FILE_NAME}.zip"
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Result $((i+1)): $FILE_NAME"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Extract summary statistics from the backtest using freqtrade
    # Create a temporary symlink to the specific result file
    TEMP_LINK="$BACKTEST_DIR/.last_result.json"
    rm -f "$TEMP_LINK"
    
    # Unzip to get the stats
    if [ -f "$ZIP_FILE" ]; then
      unzip -q -o "$ZIP_FILE" -d "$BACKTEST_DIR/temp_$i" 2>/dev/null
      
      # Find the strategy JSON file and extract metrics
      STRATEGY_FILE=$(find "$BACKTEST_DIR/temp_$i" -name "*strategy*.json" -o -name "*.json" | head -1)
      
      if [ -f "$STRATEGY_FILE" ] && command -v jq &> /dev/null; then
        # Get first strategy key dynamically
        STRAT_KEY=$(jq -r 'keys[0]' "$STRATEGY_FILE" 2>/dev/null)
        
        if [ "$STRAT_KEY" != "null" ] && [ -n "$STRAT_KEY" ]; then
          TOTAL_TRADES=$(jq -r ".\"$STRAT_KEY\".results_per_pair[-1].trades // \"N/A\"" "$STRATEGY_FILE" 2>/dev/null)
          PROFIT_TOTAL=$(jq -r ".\"$STRAT_KEY\".results_per_pair[-1].profit_total // \"N/A\"" "$STRATEGY_FILE" 2>/dev/null)
          PROFIT_MEAN=$(jq -r ".\"$STRAT_KEY\".results_per_pair[-1].profit_mean // \"N/A\"" "$STRATEGY_FILE" 2>/dev/null)
          PROFIT_TOTAL_ABS=$(jq -r ".\"$STRAT_KEY\".results_per_pair[-1].profit_total_abs // \"N/A\"" "$STRATEGY_FILE" 2>/dev/null)
          WIN_RATE=$(jq -r ".\"$STRAT_KEY\".results_per_pair[-1].wins // 0" "$STRATEGY_FILE" 2>/dev/null)
          LOSS_RATE=$(jq -r ".\"$STRAT_KEY\".results_per_pair[-1].losses // 0" "$STRATEGY_FILE" 2>/dev/null)
          MAX_DRAWDOWN=$(jq -r ".\"$STRAT_KEY\".max_drawdown_account // \"N/A\"" "$STRATEGY_FILE" 2>/dev/null)
          
          # Calculate win percentage
          if [ "$TOTAL_TRADES" != "N/A" ] && [ "$TOTAL_TRADES" != "null" ] && [ "$TOTAL_TRADES" -gt 0 ]; then
            WIN_PCT=$(echo "scale=1; $WIN_RATE * 100 / $TOTAL_TRADES" | bc 2>/dev/null || echo "N/A")
          else
            WIN_PCT="N/A"
          fi
          
          echo "  📊 Total Trades:      $TOTAL_TRADES"
          echo "  💰 Profit Total:      ${PROFIT_TOTAL}%"
          echo "  📈 Profit Mean:       ${PROFIT_MEAN}%"
          echo "  💵 Profit Total Abs:  $PROFIT_TOTAL_ABS USDT"
          echo "  ✅ Wins / ❌ Losses:  $WIN_RATE / $LOSS_RATE"
          echo "  🎯 Win Rate:          ${WIN_PCT}%"
          echo "  📉 Max Drawdown:      ${MAX_DRAWDOWN}%"
        else
          echo "  ℹ️  Unable to parse strategy data"
        fi
      else
        echo "  ℹ️  Run 'freqtrade backtesting-show' for detailed stats"
      fi
      
      # Cleanup temp directory
      rm -rf "$BACKTEST_DIR/temp_$i"
    else
      echo "  ⚠️  Zip file not found: $ZIP_FILE"
    fi
    
    echo ""
  done
  
  echo "========================================="
  echo ""
  echo "💡 To view full detailed comparison:"
  echo "   freqtrade backtesting-show"
  echo ""
}

# Function to compare hyperopt results
compare_hyperopt_results() {
  echo ""
  echo "========================================="
  echo "  Compare Hyperopt Results"
  echo "========================================="
  echo ""
  
  HYPEROPT_DIR="user_data/hyperopt_results"
  
  if [ ! -d "$HYPEROPT_DIR" ]; then
    echo "Error: Hyperopt results directory not found!"
    echo "Please run hyperopt first (option 2 or 4)."
    return 1
  fi
  
  # Find last 3 hyperopt result files
  mapfile -t RESULT_FILES < <(ls -t "$HYPEROPT_DIR"/*.pkl 2>/dev/null | head -3)
  
  if [ ${#RESULT_FILES[@]} -eq 0 ]; then
    echo "No hyperopt results found in $HYPEROPT_DIR"
    echo "Please run hyperopt first (option 2 or 4)."
    return 1
  fi
  
  if [ ${#RESULT_FILES[@]} -lt 2 ]; then
    echo "Not enough hyperopt results to compare (found ${#RESULT_FILES[@]}, need at least 2)."
    echo "Please run more hyperopt sessions first."
    return 1
  fi
  
  echo "Comparing the last ${#RESULT_FILES[@]} hyperopt results:"
  echo ""
  for i in "${!RESULT_FILES[@]}"; do
    FILE_NAME=$(basename "${RESULT_FILES[$i]}")
    FILE_DATE=$(stat -c %y "${RESULT_FILES[$i]}" 2>/dev/null | cut -d' ' -f1,2 | cut -d'.' -f1)
    echo "  $((i+1))) $FILE_NAME"
    echo "      Date: $FILE_DATE"
  done
  
  echo ""
  echo "========================================="
  echo "Comparison Summary:"
  echo "========================================="
  echo ""
  
  # Show best result from each hyperopt run
  for i in "${!RESULT_FILES[@]}"; do
    FILE_NAME=$(basename "${RESULT_FILES[$i]}")
    echo "Result $((i+1)): $FILE_NAME"
    echo "----------------------------------------"
    
    freqtrade hyperopt-show \
      --best \
      --no-header \
      --hyperopt-filename "$FILE_NAME" 2>/dev/null | head -20
    
    echo ""
  done
  
  echo "========================================="
  echo ""
  echo "To view detailed comparison:"
  echo "  - Compare top epochs from each run"
  echo "  - Use option 7 to view individual results"
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
  8)
    compare_backtest_results
    ;;
  9)
    compare_hyperopt_results
    ;;
  *)
    echo "Invalid choice. Please run the script again and select 1-9."
    exit 1
    ;;
esac

echo ""
echo "Script completed!"
