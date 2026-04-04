import pytest
import pandas as pd
from engine.phase_fsm import PhaseFSM, PhaseState
from unittest.mock import Mock

def test_emergency_reversal_trigger():
    # 模拟外部依赖
    storage = Mock()
    storage.get_current_phase.return_value = {"phase_code": "ACC-C", "start_date": "2023-01-01"}
    
    config = {}
    fsm = PhaseFSM(config, storage)
    
    # 构造含紧急反转结果的 ce_result
    ce_result = {
        "reversal_triggered": True,
        "reversal_target": "DIS-C",
        "reversal_reasoning": "积分>71触发红牌"
    }
    
    df = pd.DataFrame({"trade_date": ["2023-01-05"], "close": [10.0], "high": [10.2], "low": [9.8]})
    
    # 执行处理
    new_state = fsm.process_bar("000001.SZ", df, signals=[], ce_result=ce_result, timeframe="daily")
    
    assert new_state.phase_code == "DIS-C"
    assert "紧急反转: 积分>71触发红牌" in new_state.evidence_chain[-1]
