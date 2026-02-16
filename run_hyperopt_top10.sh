#!/bin/bash

# Activate virtual environment
source .venv/bin/activate

# Configuration
STRATEGY="NostalgiaForInfinityX7"
CONFIG_PAIRLIST="configs/pairlist-hyperopt-static-binance-futures-usdt.json"
TIMERANGE="20250101-20260201"
TIMEFRAMES="5m 1h 15m 4h 1d"

# Menu for user selection
echo "========================================="
echo "  Test9201 Strategy - Trading Tools"
echo "========================================="
echo ""
echo "Select an option:"
echo "  1) Download data only"
echo "  2) Run hyperopt (800 epochs)"
echo "  3) Run backtest"
echo "  4) Download data + hyperopt"
echo "  5) Download data + backtest"
echo "  6) Show backtest results"
echo "  7) Show hyperopt results"
echo "  8) Compare last 3 backtest results"
echo "  9) Compare last 3 hyperopt results"
echo " 10) Run multiple backtests from JSON config"
echo ""
read -p "Enter your choice [1-10]: " choice

# Function to download data
download_data() {
  echo ""
  echo "Downloading data from 20250101..."
  
  # Calculate end date (today)
  END_DATE=$(date +%Y%m%d)
  DOWNLOAD_TIMERANGE="20250101-${END_DATE}"
  
  echo "Using timerange: $DOWNLOAD_TIMERANGE"
  
  freqtrade download-data \
    --exchange binance \
    --trading-mode futures \
    --config "$CONFIG_PAIRLIST" \
    --timeframes $TIMEFRAMES \
    --timerange "$DOWNLOAD_TIMERANGE"
  echo "Data download completed!"
}

# Function to run hyperopt
run_hyperopt() {
  echo ""
  echo "Starting hyperopt with 800 epochs..."
  echo "Using timerange: $TIMERANGE"
  
  freqtrade hyperopt \
    --hyperopt-loss SharpeHyperOptLoss \
    --strategy "$STRATEGY" \
    --config "$CONFIG_PAIRLIST" \
    --timerange "$TIMERANGE" \
    --epochs 800 \
    --spaces buy \
    --random-state 42 \
    -j 2
  echo ""
  echo "Hyperopt completed!"
}

# Function to run backtest
run_backtest() {
  echo ""
  echo "Starting backtest..."
  echo "Using timerange: $TIMERANGE"
  
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

# Function to run multiple backtests with parameters from JSON
run_multi_backtest() {
  echo ""
  echo "========================================="
  echo "  Multi-Backtest with JSON Parameters"
  echo "========================================="
  echo ""
  
  # Check if jq is installed
  if ! command -v jq &> /dev/null; then
    echo "Error: jq is not installed. Please install it first:"
    echo "  sudo apt-get install jq  # For Debian/Ubuntu"
    echo "  brew install jq          # For macOS"
    return 1
  fi
  
  # Prompt for JSON file path
  echo "Available JSON parameter files:"
  echo ""
  
  # Search for JSON files in common locations
  PARAM_FILES=()
  if [ -d "user_data/strategies" ]; then
    mapfile -t STRATEGY_JSONS < <(find user_data/strategies -name "*.json" 2>/dev/null)
    PARAM_FILES+=("${STRATEGY_JSONS[@]}")
  fi
  if [ -d "configs" ]; then
    mapfile -t CONFIG_JSONS < <(find configs -name "*config*.json" -o -name "*param*.json" 2>/dev/null)
    PARAM_FILES+=("${CONFIG_JSONS[@]}")
  fi
  
  # Add root directory JSON files
  mapfile -t ROOT_JSONS < <(find . -maxdepth 1 -name "*param*.json" -o -name "*config*.json" 2>/dev/null)
  PARAM_FILES+=("${ROOT_JSONS[@]}")
  
  if [ ${#PARAM_FILES[@]} -eq 0 ]; then
    echo "No JSON parameter files found."
    echo ""
    read -p "Enter path to JSON file: " JSON_FILE
  else
    for i in "${!PARAM_FILES[@]}"; do
      echo "  $((i+1))) ${PARAM_FILES[$i]}"
    done
    echo ""
    read -p "Select a file [1-${#PARAM_FILES[@]}] or enter custom path: " selection
    
    if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le ${#PARAM_FILES[@]} ]; then
      JSON_FILE="${PARAM_FILES[$((selection-1))]}"
    else
      JSON_FILE="$selection"
    fi
  fi
  
  # Validate JSON file exists
  if [ ! -f "$JSON_FILE" ]; then
    echo "Error: File '$JSON_FILE' not found!"
    return 1
  fi
  
  echo ""
  echo "Using parameters from: $JSON_FILE"
  echo ""
  
  # Check JSON structure - detect if it has test_configurations array
  HAS_TEST_CONFIGS=$(jq -r 'has("test_configurations")' "$JSON_FILE" 2>/dev/null)
  
  # Prepare test parameters
  declare -a TEST_LEVERAGES
  declare -a TEST_LEVERAGES_GRIND
  declare -a TEST_LEVERAGES_REBUY
  declare -a TEST_LABELS
  
  if [ "$HAS_TEST_CONFIGS" == "true" ]; then
    # New format: multiple configurations in array
    echo "Detected multi-configuration JSON format"
    echo ""
    
    # Get total number of configurations
    TOTAL_CONFIGS=$(jq -r '.test_configurations | length' "$JSON_FILE" 2>/dev/null)
    echo "Found $TOTAL_CONFIGS test configurations in file"
    echo ""
    
    # Show available configurations
    echo "Available test configurations:"
    echo ""
    for ((i=0; i<TOTAL_CONFIGS; i++)); do
      TEST_NAME=$(jq -r ".test_configurations[$i].name" "$JSON_FILE" 2>/dev/null)
      LEV=$(jq -r ".test_configurations[$i].params.futures_mode_leverage" "$JSON_FILE" 2>/dev/null)
      LEV_GRIND=$(jq -r ".test_configurations[$i].params.futures_mode_leverage_grind_mode" "$JSON_FILE" 2>/dev/null)
      LEV_REBUY=$(jq -r ".test_configurations[$i].params.futures_mode_leverage_rebuy_mode" "$JSON_FILE" 2>/dev/null)
      echo "  $((i+1))) $TEST_NAME"
      echo "      Leverage: $LEV, Grind: $LEV_GRIND, Rebuy: $LEV_REBUY"
    done
    
    echo ""
    echo "Selection options:"
    echo "  1) Run ALL $TOTAL_CONFIGS configurations"
    echo "  2) Run specific range (e.g., 1-10)"
    echo "  3) Run specific tests (e.g., 1,5,10,15)"
    echo ""
    read -p "Enter your choice [1-3]: " SELECTION_MODE
    
    declare -a SELECTED_INDICES
    
    case $SELECTION_MODE in
      1)
        # Run all
        for ((i=0; i<TOTAL_CONFIGS; i++)); do
          SELECTED_INDICES+=($i)
        done
        ;;
      2)
        # Run range
        read -p "Enter range (e.g., 1-10): " RANGE_INPUT
        START=$(echo "$RANGE_INPUT" | cut -d'-' -f1)
        END=$(echo "$RANGE_INPUT" | cut -d'-' -f2)
        
        # Validate and adjust to 0-based index
        START=$((START - 1))
        END=$((END - 1))
        
        if [ $START -lt 0 ]; then START=0; fi
        if [ $END -ge $TOTAL_CONFIGS ]; then END=$((TOTAL_CONFIGS - 1)); fi
        
        for ((i=START; i<=END; i++)); do
          SELECTED_INDICES+=($i)
        done
        ;;
      3)
        # Run specific tests
        read -p "Enter test numbers separated by comma (e.g., 1,5,10): " SPECIFIC_TESTS
        IFS=',' read -ra TEST_NUMS <<< "$SPECIFIC_TESTS"
        for num in "${TEST_NUMS[@]}"; do
          # Convert to 0-based index
          idx=$((num - 1))
          if [ $idx -ge 0 ] && [ $idx -lt $TOTAL_CONFIGS ]; then
            SELECTED_INDICES+=($idx)
          fi
        done
        ;;
      *)
        echo "Invalid choice. Running first 5 tests."
        for ((i=0; i<5 && i<TOTAL_CONFIGS; i++)); do
          SELECTED_INDICES+=($i)
        done
        ;;
    esac
    
    NUM_TESTS=${#SELECTED_INDICES[@]}
    
    echo ""
    echo "Selected $NUM_TESTS tests to run:"
    echo ""
    
    # Load selected configurations
    for i in "${!SELECTED_INDICES[@]}"; do
      idx=${SELECTED_INDICES[$i]}
      TEST_NAME=$(jq -r ".test_configurations[$idx].name" "$JSON_FILE" 2>/dev/null)
      LEV=$(jq -r ".test_configurations[$idx].params.futures_mode_leverage" "$JSON_FILE" 2>/dev/null)
      LEV_GRIND=$(jq -r ".test_configurations[$idx].params.futures_mode_leverage_grind_mode" "$JSON_FILE" 2>/dev/null)
      LEV_REBUY=$(jq -r ".test_configurations[$idx].params.futures_mode_leverage_rebuy_mode" "$JSON_FILE" 2>/dev/null)
      
      TEST_LEVERAGES[$((i+1))]="$LEV"
      TEST_LEVERAGES_GRIND[$((i+1))]="$LEV_GRIND"
      TEST_LEVERAGES_REBUY[$((i+1))]="$LEV_REBUY"
      TEST_LABELS[$((i+1))]="Test $((i+1)): $TEST_NAME (L=$LEV, G=$LEV_GRIND, R=$LEV_REBUY)"
      
      echo "  $((i+1))) $TEST_NAME"
      echo "      Leverage: $LEV, Grind: $LEV_GRIND, Rebuy: $LEV_REBUY"
    done
    
  else
    # Old format: single configuration with variation modes
    # Extract leverage parameters from JSON
    LEVERAGE=$(jq -r '.params.buy.futures_mode_leverage // empty' "$JSON_FILE" 2>/dev/null)
    LEVERAGE_GRIND=$(jq -r '.params.buy.futures_mode_leverage_grind_mode // empty' "$JSON_FILE" 2>/dev/null)
    LEVERAGE_REBUY=$(jq -r '.params.buy.futures_mode_leverage_rebuy_mode // empty' "$JSON_FILE" 2>/dev/null)
    
    # Display extracted parameters
    echo "Extracted parameters:"
    echo "  - futures_mode_leverage: ${LEVERAGE:-Not found}"
    echo "  - futures_mode_leverage_grind_mode: ${LEVERAGE_GRIND:-Not found}"
    echo "  - futures_mode_leverage_rebuy_mode: ${LEVERAGE_REBUY:-Not found}"
    echo ""
    
    # Check if we have valid parameters
    if [ -z "$LEVERAGE" ] && [ -z "$LEVERAGE_GRIND" ] && [ -z "$LEVERAGE_REBUY" ]; then
      echo "Error: No leverage parameters found in JSON file!"
      echo "Expected structure:"
      echo '  Format 1 (Single config with variations):'
      echo '  {'
      echo '    "params": {'
      echo '      "buy": {'
      echo '        "futures_mode_leverage": 12,'
      echo '        "futures_mode_leverage_grind_mode": 4,'
      echo '        "futures_mode_leverage_rebuy_mode": 4'
      echo '      }'
      echo '    }'
      echo '  }'
      echo ''
      echo '  Format 2 (Multiple predefined configs):'
      echo '  {'
      echo '    "test_configurations": ['
      echo '      {'
      echo '        "name": "Test Name",'
      echo '        "params": {'
      echo '          "futures_mode_leverage": 12,'
      echo '          "futures_mode_leverage_grind_mode": 4,'
      echo '          "futures_mode_leverage_rebuy_mode": 4'
      echo '        }'
      echo '      }'
      echo '    ]'
      echo '  }'
      return 1
    fi
    
    # Prompt for test configurations
    echo "Configure multiple backtest runs:"
    echo ""
    read -p "How many backtest variations to run? [1-10]: " NUM_TESTS
    
    # Validate number
    if ! [[ "$NUM_TESTS" =~ ^[0-9]+$ ]] || [ "$NUM_TESTS" -lt 1 ] || [ "$NUM_TESTS" -gt 10 ]; then
      echo "Invalid number. Using 3 tests."
      NUM_TESTS=3
    fi
    
    echo ""
    echo "Select variation mode:"
    echo "  1) Use exact parameters from JSON (same for all runs)"
    echo "  2) Multiply leverage by factors [0.5, 1.0, 1.5, 2.0, etc.]"
    echo "  3) Add/subtract values [-2, -1, 0, +1, +2, etc.]"
    echo "  4) Custom leverage values (prompt for each)"
    echo ""
    read -p "Enter variation mode [1-4]: " VARIATION_MODE
    
    case $VARIATION_MODE in
      1)
        # Use same parameters for all tests
        for ((i=1; i<=NUM_TESTS; i++)); do
          TEST_LEVERAGES[$i]="$LEVERAGE"
          TEST_LEVERAGES_GRIND[$i]="$LEVERAGE_GRIND"
          TEST_LEVERAGES_REBUY[$i]="$LEVERAGE_REBUY"
          TEST_LABELS[$i]="Test $i (leverage=$LEVERAGE)"
        done
        ;;
      2)
        # Multiply by factors
        FACTORS=(0.5 0.75 1.0 1.25 1.5 1.75 2.0 2.5 3.0 4.0)
        for ((i=1; i<=NUM_TESTS; i++)); do
          FACTOR=${FACTORS[$((i-1))]}
          if [ -z "$FACTOR" ]; then
            FACTOR=1.0
          fi
          TEST_LEV=$(echo "scale=2; $LEVERAGE * $FACTOR" | bc)
          TEST_LEV_GRIND=$(echo "scale=2; $LEVERAGE_GRIND * $FACTOR" | bc)
          TEST_LEV_REBUY=$(echo "scale=2; $LEVERAGE_REBUY * $FACTOR" | bc)
          TEST_LEVERAGES[$i]="$TEST_LEV"
          TEST_LEVERAGES_GRIND[$i]="$TEST_LEV_GRIND"
          TEST_LEVERAGES_REBUY[$i]="$TEST_LEV_REBUY"
          TEST_LABELS[$i]="Test $i (leverage=${TEST_LEV}, factor=${FACTOR}x)"
        done
        ;;
      3)
        # Add/subtract values
        ADJUSTMENTS=(-2 -1 0 1 2 3 4 5 6 8)
        for ((i=1; i<=NUM_TESTS; i++)); do
          ADJ=${ADJUSTMENTS[$((i-1))]}
          if [ -z "$ADJ" ]; then
            ADJ=0
          fi
          TEST_LEV=$(echo "$LEVERAGE + $ADJ" | bc)
          TEST_LEV_GRIND=$(echo "$LEVERAGE_GRIND + $ADJ" | bc)
          TEST_LEV_REBUY=$(echo "$LEVERAGE_REBUY + $ADJ" | bc)
          TEST_LEVERAGES[$i]="$TEST_LEV"
          TEST_LEVERAGES_GRIND[$i]="$TEST_LEV_GRIND"
          TEST_LEVERAGES_REBUY[$i]="$TEST_LEV_REBUY"
          TEST_LABELS[$i]="Test $i (leverage=${TEST_LEV}, base+${ADJ})"
        done
        ;;
      4)
        # Custom values
        echo ""
        for ((i=1; i<=NUM_TESTS; i++)); do
          read -p "Enter leverage value for test $i [default=$LEVERAGE]: " CUSTOM_LEV
          if [ -z "$CUSTOM_LEV" ]; then
            CUSTOM_LEV=$LEVERAGE
          fi
          read -p "Enter grind leverage for test $i [default=$LEVERAGE_GRIND]: " CUSTOM_LEV_GRIND
          if [ -z "$CUSTOM_LEV_GRIND" ]; then
            CUSTOM_LEV_GRIND=$LEVERAGE_GRIND
          fi
          read -p "Enter rebuy leverage for test $i [default=$LEVERAGE_REBUY]: " CUSTOM_LEV_REBUY
          if [ -z "$CUSTOM_LEV_REBUY" ]; then
            CUSTOM_LEV_REBUY=$LEVERAGE_REBUY
          fi
          TEST_LEVERAGES[$i]="$CUSTOM_LEV"
          TEST_LEVERAGES_GRIND[$i]="$CUSTOM_LEV_GRIND"
          TEST_LEVERAGES_REBUY[$i]="$CUSTOM_LEV_REBUY"
          TEST_LABELS[$i]="Test $i (leverage=$CUSTOM_LEV)"
        done
        ;;
      *)
        echo "Invalid mode. Using exact parameters from JSON."
        for ((i=1; i<=NUM_TESTS; i++)); do
          TEST_LEVERAGES[$i]="$LEVERAGE"
          TEST_LEVERAGES_GRIND[$i]="$LEVERAGE_GRIND"
          TEST_LEVERAGES_REBUY[$i]="$LEVERAGE_REBUY"
          TEST_LABELS[$i]="Test $i (leverage=$LEVERAGE)"
        done
        ;;
    esac
  fi
  
  echo ""
  echo "Execution mode:"
  echo "  1) Sequential (run tests one after another)"
  echo "  2) Parallel (run all tests simultaneously)"
  echo ""
  read -p "Enter execution mode [1-2, default=1]: " EXEC_MODE
  
  if [ -z "$EXEC_MODE" ]; then
    EXEC_MODE=1
  fi
  
  echo ""
  echo "========================================="
  echo "Starting $NUM_TESTS backtest runs..."
  if [ "$EXEC_MODE" == "2" ]; then
    echo "Mode: PARALLEL"
    echo "Note: All tests will run simultaneously"
  else
    echo "Mode: SEQUENTIAL"
  fi
  echo "========================================="
  echo ""
  
  # Prepare log directory for parallel execution
  LOG_DIR="user_data/backtest_logs"
  mkdir -p "$LOG_DIR"
  
  # Array to store background process PIDs
  declare -a PIDS
  
  # Run each backtest
  for ((i=1; i<=NUM_TESTS; i++)); do
    LEV="${TEST_LEVERAGES[$i]}"
    
    # Get grind and rebuy leverage from arrays
    LEV_GRIND="${TEST_LEVERAGES_GRIND[$i]}"
    LEV_REBUY="${TEST_LEVERAGES_REBUY[$i]}"
    
    # Create temporary config file with strategy parameters
    TEMP_CONFIG="$LOG_DIR/temp_config_test${i}.json"
    cat > "$TEMP_CONFIG" << EOF
{
  "strategy_name": "$STRATEGY",
  "params": {
    "buy": {
      "futures_mode_leverage": $LEV,
      "futures_mode_leverage_grind_mode": $LEV_GRIND,
      "futures_mode_leverage_rebuy_mode": $LEV_REBUY
    }
  }
}
EOF
    
    if [ "$EXEC_MODE" == "2" ]; then
      # Parallel execution
      LOG_FILE="$LOG_DIR/backtest_test${i}_lev${LEV}.log"
      
      echo "🚀 Starting Test $i in background (leverage=$LEV)"
      echo "   Log file: $LOG_FILE"
      
      # Run in background and redirect output to log file
      (
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" > "$LOG_FILE"
        echo "${TEST_LABELS[$i]}" >> "$LOG_FILE"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
        echo "Parameters:" >> "$LOG_FILE"
        echo "  - futures_mode_leverage: $LEV" >> "$LOG_FILE"
        [ -n "$LEV_GRIND" ] && echo "  - futures_mode_leverage_grind_mode: $LEV_GRIND" >> "$LOG_FILE"
        [ -n "$LEV_REBUY" ] && echo "  - futures_mode_leverage_rebuy_mode: $LEV_REBUY" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
        echo "Started at: $(date)" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
        
        freqtrade backtesting \
          --strategy "$STRATEGY" \
          --config "$CONFIG_PAIRLIST" \
          --config "$TEMP_CONFIG" \
          --timerange "$TIMERANGE" \
          --breakdown month >> "$LOG_FILE" 2>&1
        
        EXIT_CODE=$?
        echo "" >> "$LOG_FILE"
        echo "Completed at: $(date)" >> "$LOG_FILE"
        echo "Exit code: $EXIT_CODE" >> "$LOG_FILE"
        
        if [ $EXIT_CODE -eq 0 ]; then
          echo "✓ Test $i completed successfully!" >> "$LOG_FILE"
        else
          echo "✗ Test $i failed with exit code $EXIT_CODE" >> "$LOG_FILE"
        fi
        
        # Cleanup temp config
        rm -f "$TEMP_CONFIG"
        
        exit $EXIT_CODE
      ) &
      
      PIDS[$i]=$!
      echo "   PID: ${PIDS[$i]}"
      echo ""
      
    else
      # Sequential execution
      echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
      echo "${TEST_LABELS[$i]}"
      echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
      echo ""
      
      echo "Parameters:"
      echo "  - futures_mode_leverage: $LEV"
      [ -n "$LEV_GRIND" ] && echo "  - futures_mode_leverage_grind_mode: $LEV_GRIND"
      [ -n "$LEV_REBUY" ] && echo "  - futures_mode_leverage_rebuy_mode: $LEV_REBUY"
      echo ""
      
      # Run backtest
      freqtrade backtesting \
        --strategy "$STRATEGY" \
        --config "$CONFIG_PAIRLIST" \
        --config "$TEMP_CONFIG" \
        --timerange "$TIMERANGE" \
        --breakdown month
      
      # Cleanup temp config
      rm -f "$TEMP_CONFIG"
      
      echo ""
      echo "✓ Test $i completed!"
      echo ""
      
      # Add a small delay between runs
      if [ $i -lt $NUM_TESTS ]; then
        sleep 2
      fi
    fi
  done
  
  # Wait for parallel processes to complete
  if [ "$EXEC_MODE" == "2" ]; then
    echo "========================================="
    echo "Waiting for all parallel tests to complete..."
    echo "========================================="
    echo ""
    
    FAILED_TESTS=0
    COMPLETED_TESTS=0
    
    for ((i=1; i<=NUM_TESTS; i++)); do
      PID=${PIDS[$i]}
      
      if [ -n "$PID" ]; then
        echo "⏳ Waiting for Test $i (PID: $PID)..."
        
        # Wait for the process and get exit code
        wait $PID
        EXIT_CODE=$?
        
        if [ $EXIT_CODE -eq 0 ]; then
          echo "✓ Test $i completed successfully!"
          ((COMPLETED_TESTS++))
        else
          echo "✗ Test $i failed with exit code $EXIT_CODE"
          ((FAILED_TESTS++))
        fi
        echo ""
      fi
    done
    
    echo "========================================="
    echo "Parallel Execution Summary"
    echo "========================================="
    echo "  Total tests: $NUM_TESTS"
    echo "  Completed: $COMPLETED_TESTS"
    echo "  Failed: $FAILED_TESTS"
    echo ""
    
    if [ $FAILED_TESTS -gt 0 ]; then
      echo "⚠️  Some tests failed. Check log files in $LOG_DIR"
      echo ""
    fi
    
    echo "Log files location: $LOG_DIR"
    echo ""
    echo "To view logs:"
    for ((i=1; i<=NUM_TESTS; i++)); do
      LEV="${TEST_LEVERAGES[$i]}"
      LOG_FILE="$LOG_DIR/backtest_test${i}_lev${LEV}.log"
      if [ -f "$LOG_FILE" ]; then
        echo "  Test $i: cat $LOG_FILE"
      fi
    done
    echo ""
  else
    echo "========================================="
    echo "All $NUM_TESTS backtests completed!"
    echo "========================================="
    echo ""
  fi
  
  echo "Results saved to user_data/backtest_results/"
  echo "Use option 6 or 8 to view and compare results."
  echo ""
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
      
      # Find the main backtest result JSON file (not config or strategy params)
      RESULT_FILE=$(find "$BACKTEST_DIR/temp_$i" -name "backtest-result-*.json" ! -name "*_config.json" ! -name "*_${STRATEGY}.json" | head -1)
      
      if [ -f "$RESULT_FILE" ] && command -v jq &> /dev/null; then
        # Extract metrics from strategy_comparison array (first element)
        TOTAL_TRADES=$(jq -r '.strategy_comparison[0].trades // "N/A"' "$RESULT_FILE" 2>/dev/null)
        PROFIT_TOTAL=$(jq -r '.strategy_comparison[0].profit_total_pct // "N/A"' "$RESULT_FILE" 2>/dev/null)
        PROFIT_MEAN=$(jq -r '.strategy_comparison[0].profit_mean_pct // "N/A"' "$RESULT_FILE" 2>/dev/null)
        PROFIT_TOTAL_ABS=$(jq -r '.strategy_comparison[0].profit_total_abs // "N/A"' "$RESULT_FILE" 2>/dev/null)
        WIN_RATE=$(jq -r '.strategy_comparison[0].wins // 0' "$RESULT_FILE" 2>/dev/null)
        LOSS_RATE=$(jq -r '.strategy_comparison[0].losses // 0' "$RESULT_FILE" 2>/dev/null)
        MAX_DRAWDOWN=$(jq -r '.strategy_comparison[0].max_drawdown_account // "N/A"' "$RESULT_FILE" 2>/dev/null)
        WINRATE_PCT=$(jq -r '.strategy_comparison[0].winrate // "N/A"' "$RESULT_FILE" 2>/dev/null)
        
        # Format winrate percentage
        if [ "$WINRATE_PCT" != "N/A" ] && [ "$WINRATE_PCT" != "null" ]; then
          WIN_PCT=$(echo "scale=1; $WINRATE_PCT * 100" | bc 2>/dev/null || echo "$WINRATE_PCT")
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
        echo "  ℹ️  Unable to parse result file"
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
  10)
    run_multi_backtest
    ;;
  *)
    echo "Invalid choice. Please run the script again and select 1-10."
    exit 1
    ;;
esac

echo ""
echo "Script completed!"
