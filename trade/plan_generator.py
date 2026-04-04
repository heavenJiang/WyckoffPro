"""
trade/plan_generator.py — 交易计划生成器
基于建议+风险管理自动生成完整交易计划。
"""
from __future__ import annotations
from datetime import datetime
from typing import Dict, Optional
from trade.risk_manager import RiskManager
from loguru import logger


class TradePlanGenerator:
    """交易计划生成器"""

    def __init__(self, config: dict, storage, risk_manager: RiskManager):
        self.config = config
        self.storage = storage
        self.risk_mgr = risk_manager

    def generate(self, stock_code: str, advice: dict, channel_levels,
                 pnf_targets: dict = None, portfolio_value: float = 0) -> Optional[Dict]:
        """
        根据投资建议生成交易计划。
        返回 plan dict 或 None（建议为WAIT/HOLD时不生成）。
        """
        advice_type = advice.get("advice_type", "WAIT")
        if advice_type in ("WAIT", "HOLD", "WATCH"):
            return None

        tp = advice.get("trade_plan", {})
        entry = tp.get("entry_price", 0) or (getattr(channel_levels, "support_1", 0) * 1.01 if channel_levels else 0)
        stop = tp.get("stop_loss", 0) or (getattr(channel_levels, "support_2", 0) * 0.98 if channel_levels else 0)
        target_1 = tp.get("target_1", 0) or (getattr(channel_levels, "resistance_1", 0) if channel_levels else 0)
        target_2 = tp.get("target_2", 0) or (getattr(channel_levels, "resistance_2", 0) if channel_levels else 0)

        # P&F目标覆盖
        if pnf_targets:
            pnf_t = pnf_targets.get("count_target", 0)
            if pnf_t > entry and pnf_t > target_1:
                target_2 = pnf_t

        # 风险验证
        if entry <= stop:
            logger.warning(f"[{stock_code}] 入场价{entry}<=止损{stop}，计划无效")
            return None

        size_info = {}
        if portfolio_value > 0:
            size_info = self.risk_mgr.calc_position_size(entry, stop, portfolio_value, target_1)

        rr = round((target_1 - entry) / (entry - stop), 1) if entry > stop and target_1 > entry else 0

        plan = {
            "stock_code": stock_code,
            "direction": "LONG" if advice_type in ("STRONG_BUY", "BUY") else "SHORT",
            "entry_mode": tp.get("entry_mode", "限价"),
            "entry_price": round(entry, 2),
            "stop_loss": round(stop, 2),
            "target_1": round(target_1, 2),
            "target_2": round(target_2, 2),
            "rr_ratio": rr,
            "position_pct": size_info.get("position_pct", tp.get("position_pct", 0)),
            "status": "DRAFT",
            "linked_advice_id": advice.get("id"),
            "notes": f"建议类型:{advice_type} | {advice.get('summary', '')}",
        }

        # 保存到DB
        plan_id = self.storage.save_trade_plan(plan)
        plan["id"] = plan_id
        logger.info(f"[{stock_code}] 生成交易计划 #{plan_id}：入场{entry} 止损{stop} 目标{target_1} RR={rr}")
        return plan
