import logging
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from pandas import DataFrame

# --- CẤU HÌNH IMPORT TỰ ĐỘNG ---
# Thêm đường dẫn hiện tại để tìm thấy file NostalgiaForInfinityX7.py
sys.path.append(str(Path(__file__).parent))

try:
    from NostalgiaForInfinityX7 import NostalgiaForInfinityX7
except ImportError:
    print("LỖI: Không tìm thấy file NostalgiaForInfinityX7.py trong thư mục strategies!")
    # Tạo class giả để tránh lỗi khi compile nếu thiếu file
    class NostalgiaForInfinityX7(IStrategy):
        pass

log = logging.getLogger(__name__)

# Wrapper cho DataProvider để đảm bảo tất cả dataframe có cột 'date'
class DataProviderWrapper:
    """Wrapper để đảm bảo tất cả dataframe trả về có cột 'date'"""
    def __init__(self, dp):
        self._dp = dp
    
    def __getattr__(self, name):
        """Forward tất cả các phương thức khác tới DataProvider gốc"""
        return getattr(self._dp, name)
    
    def _ensure_date_column(self, df):
        """Helper method to ensure dataframe has 'date' column"""
        if df is None or df.empty:
            return df
        
        if 'date' not in df.columns:
            # Always make a copy to avoid modifying the original
            df = df.copy()
            
            # Save original columns to detect which one was added by reset_index
            orig_cols = set(df.columns)
            
            # Reset index to make it a column
            df.reset_index(drop=False, inplace=True)
            
            # Find the new column created by reset_index
            new_cols = set(df.columns) - orig_cols
            
            if new_cols and 'date' not in df.columns:
                # Rename the new column to 'date'
                new_col_name = list(new_cols)[0]
                df.rename(columns={new_col_name: 'date'}, inplace=True)
            elif 'date' not in df.columns and len(df.columns) > 0:
                # Fallback: if somehow no new column detected, try common names
                for possible_name in ['index', df.index.name] + list(df.columns[:1]):
                    if possible_name and possible_name in df.columns and possible_name != 'date':
                        df.rename(columns={possible_name: 'date'}, inplace=True)
                        break
        
        return df
    
    def get_pair_dataframe(self, pair, timeframe):
        """Override để thêm cột 'date' vào dataframe"""
        df = self._dp.get_pair_dataframe(pair, timeframe)
        return self._ensure_date_column(df)
    
    def get_analyzed_dataframe(self, pair, timeframe):
        """Override để thêm cột 'date' vào analyzed dataframe"""
        if hasattr(self._dp, 'get_analyzed_dataframe'):
            df, last_update = self._dp.get_analyzed_dataframe(pair, timeframe)
            df = self._ensure_date_column(df)
            return df, last_update
        return None, None

class NFIX7_FreqAI(IStrategy):
    """
    Chiến thuật FreqAI Wrapper cho NostalgiaForInfinityX7.
    Sử dụng toàn bộ logic của NFIX7 làm đầu vào cho AI.
    """
    INTERFACE_VERSION = 3
    
    # Cấu hình cơ bản (nên đồng bộ với NFIX7 hoặc tùy chỉnh cho AI)
    minimal_roi = {"0": 0.1, "30": 0.05, "60": 0.01}
    stoploss = -0.25 
    timeframe = '5m'
    
    # Enable short trading
    can_short = True
    
    # Khai báo biến chứa chiến thuật gốc
    orig_strat = None

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        
        # Khởi tạo chiến thuật NFIX7 bên trong
        # Truyền config vào để nó hoạt động đúng như bản gốc
        self.orig_strat = NostalgiaForInfinityX7(config)
        
        # Kế thừa các tham số quan trọng từ NFIX7
        self.startup_candle_count = self.orig_strat.startup_candle_count
        self.process_only_new_candles = self.orig_strat.process_only_new_candles

    def bot_start(self, **kwargs) -> None:
        """
        Gắn DataProvider (dp) cho chiến thuật con để nó lấy được dữ liệu thị trường
        """
        if self.dp:
            # Wrap DataProvider để đảm bảo tất cả dataframe có cột 'date'
            self.orig_strat.dp = DataProviderWrapper(self.dp)
        super().bot_start(**kwargs)

    def bot_loop_start(self, current_time, **kwargs) -> None:
        """
        Gọi bot_loop_start của chiến thuật NFIX7
        """
        if self.orig_strat and hasattr(self.orig_strat, 'bot_loop_start'):
            self.orig_strat.bot_loop_start(current_time, **kwargs)
        return super().bot_loop_start(current_time, **kwargs)

    def feature_engineering_standard(self, dataframe, metadata, **kwargs):
        """
        Hàm quan trọng nhất: Biến chỉ báo của NFIX7 thành Feature cho AI
        """
        try:
            # 1. Gọi NFIX7 tính toán chỉ báo
            # Copy dataframe và đảm bảo có cột 'date'
            df_nfix7 = dataframe.copy()
            
            # Đảm bảo 'date' là cột, không phải index
            if 'date' not in df_nfix7.columns:
                # Save original columns to detect which one was added by reset_index
                orig_cols = set(df_nfix7.columns)
                
                # Reset index to make it a column
                df_nfix7.reset_index(drop=False, inplace=True)
                
                # Find the new column created by reset_index
                new_cols = set(df_nfix7.columns) - orig_cols
                
                if new_cols and 'date' not in df_nfix7.columns:
                    # Rename the new column to 'date'
                    new_col_name = list(new_cols)[0]
                    df_nfix7.rename(columns={new_col_name: 'date'}, inplace=True)
            
            # Đảm bảo orig_strat có DataProvider được wrap
            if self.dp and not isinstance(self.orig_strat.dp, DataProviderWrapper):
                self.orig_strat.dp = DataProviderWrapper(self.dp)
            
            # Gọi hàm populate_indicators của NFIX7
            # Hàm này của NFIX7 rất phức tạp, nó sẽ tạo ra RSI, BB, MFI, v.v...
            df_nfix7 = self.orig_strat.populate_indicators(df_nfix7, metadata)
            
            # 2. Gọi logic vào lệnh của NFIX7 (để lấy tín hiệu Buy làm feature)
            # AI sẽ học được: "Khi NFIX7 bảo Mua thì xác suất thắng là bao nhiêu?"
            df_nfix7 = self.orig_strat.populate_entry_trend(df_nfix7, metadata)

            # 3. Lọc và đổi tên các cột để làm đầu vào cho FreqAI
            # Các cột không nên đưa vào AI (dữ liệu thô, text)
            exclude_cols = ['date', 'open', 'high', 'low', 'close', 'volume', 'enter_tag', 'buy_tag']
            
            for col in df_nfix7.columns:
                if col not in exclude_cols:
                    # Kiểm tra kiểu dữ liệu (chỉ lấy số và boolean)
                    if df_nfix7[col].dtype.kind in 'biufc':
                        # Đặt tên cột bắt đầu bằng "%-" để FreqAI nhận diện là Extra Feature
                        feature_name = f"%-{col}_nfi"
                        
                        # Gán giá trị sang dataframe chính
                        dataframe[feature_name] = df_nfix7[col].values
                        
                        # Chuyển đổi Boolean (True/False) thành Int (1/0)
                        if dataframe[feature_name].dtype == 'bool':
                            dataframe[feature_name] = dataframe[feature_name].astype(int)
            
            # Thêm Log Volume (Feature thường dùng cho AI)
            dataframe["%-log_volume"] = np.log1p(dataframe["volume"])
            
        except Exception as e:
            log.error(f"Error in feature_engineering_standard for {metadata['pair']}: {e}")
            log.exception(e)
            # Return dataframe with minimal features on error
            dataframe["%-log_volume"] = np.log1p(dataframe["volume"])
        
        return dataframe

    def set_freqai_targets(self, dataframe, metadata, **kwargs):
        """
        Định nghĩa mục tiêu (Label) để AI học.
        Ví dụ: Dự đoán giá sẽ Tăng hay Giảm sau 20 nến?
        """
        # Classifier: Dự đoán hướng giá (Up/Down)
        dataframe["&s-up_or_down"] = np.where(
            dataframe["close"].shift(-20) > dataframe["close"], "up", "down"
        )
        return dataframe

    def populate_indicators(self, dataframe, metadata):
        # Chạy FreqAI
        dataframe = self.freqai.start(dataframe, metadata, self)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        # Logic vào lệnh dựa trên phán đoán của AI
        
        # LONG: AI dự đoán Tăng ("up")
        dataframe.loc[
            (dataframe['do_predict'] == 1) &
            (dataframe['&s-up_or_down'] == 'up'),
            'enter_long'] = 1

        # SHORT: AI dự đoán Giảm ("down")
        dataframe.loc[
            (dataframe['do_predict'] == 1) &
            (dataframe['&s-up_or_down'] == 'down'),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        # Thoát lệnh dựa trên AI
        
        # Exit LONG khi AI dự đoán Giảm
        dataframe.loc[
            (dataframe['do_predict'] == 1) &
            (dataframe['&s-up_or_down'] == 'down'),
            'exit_long'] = 1
        
        # Exit SHORT khi AI dự đoán Tăng
        dataframe.loc[
            (dataframe['do_predict'] == 1) &
            (dataframe['&s-up_or_down'] == 'up'),
            'exit_short'] = 1
                
        return dataframe