import logging
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter

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
            self.orig_strat.dp = self.dp
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
        # 1. Gọi NFIX7 tính toán chỉ báo
        # Copy dataframe để tránh xung đột dữ liệu gốc
        df_nfix7 = dataframe.copy()
        
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
                    dataframe[feature_name] = df_nfix7[col]
                    
                    # Chuyển đổi Boolean (True/False) thành Int (1/0)
                    if dataframe[feature_name].dtype == 'bool':
                        dataframe[feature_name] = dataframe[feature_name].astype(int)
        
        # Thêm Log Volume (Feature thường dùng cho AI)
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
        
        if self.freqai.is_prediction_active(dataframe, metadata):
            
            # Điều kiện 1: AI dự đoán Tăng ("up")
            # Điều kiện 2: Độ tin cậy > 0.6 (60%)
            # Điều kiện 3: Có thể kết hợp với logic NFIX7 gốc nếu muốn (ví dụ: AND %-enter_long_nfi == 1)
            
            dataframe.loc[
                (dataframe['do_predict'] == 1) &
                (dataframe['&s-up_or_down'] == 'up') &
                (dataframe['&s-up_or_down_probs'] > 0.6),
                'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        # Thoát lệnh dựa trên AI hoặc Stoploss
        if self.freqai.is_prediction_active(dataframe, metadata):
            dataframe.loc[
                (dataframe['do_predict'] == 1) &
                (dataframe['&s-up_or_down'] == 'down') &
                (dataframe['&s-up_or_down_probs'] > 0.7),
                'exit_long'] = 1
                
        return dataframe