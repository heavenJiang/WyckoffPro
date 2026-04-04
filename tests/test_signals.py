import pytest
import pandas as pd
from engine.signal_detector import SignalDetector
from engine.thresholds import Thresholds

def test_spring_detection():
    # 模拟数据
    df = pd.DataFrame({
        "trade_date": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04", "2023-01-05"],
        "open": [10.0, 9.8, 9.5, 9.2, 8.8],
        "high": [10.2, 9.9, 9.6, 9.3, 9.5],
        "low": [9.7, 9.4, 9.1, 8.7, 8.6],
        "close": [9.8, 9.5, 9.2, 8.8, 9.4], # 收回
        "volume": [100, 110, 120, 150, 80], # 缩量
    })
    
    config = {"signals": {"min_likelihood_to_record": 0.3}}
    detector = SignalDetector(config)
    thresholds = Thresholds(avg_vol_20=100, atr_20=0.5, bg_vol_threshold=80, climax_vol_threshold=200, 
                            climax_range_threshold=1.0, test_vol_ratio=0.8, st_vol_ratio=0.7, joc_vol_threshold=150)
                            
    ctx = {"tr_lower": 9.0, "has_sc": True}
    
    signals = detector.scan(df, thresholds, phase_code="ACC-B", context=ctx)
    sig_types = [s.signal_type for s in signals]
    
    # 只要包含了Spring即可
    assert "Spring" in sig_types
