"""
trade/risk_manager.py — 风险管理模块
单笔风险≤2%，总风险≤10%，T+1适配。
"""
from __future__ import annotations
from dataclasses import dataclass
from loguru import logger


@dataclass
class RiskParams:
    """风险参数"""
    entry_price: float
    stop_loss: float
    portfolio_value: float       # 账户总价值
    max_single_risk_pct: float = 2.0 / 100
    min_rr_ratio: float = 3.0


class RiskManager:
    def __init__(self, config: dict):
        cfg = config.get("risk", {})
        self.max_single_risk_pct = cfg.get("max_single_risk_pct", 2.0) / 100
        self.max_total_risk_pct = cfg.get("max_total_risk_pct", 10.0) / 100
        self.min_rr_ratio = cfg.get("min_rr_ratio", 3.0)
        self.t1_premium = cfg.get("t1_overnight_premium", 0.005)

    def calc_position_size(self, entry: float, stop: float,
                           portfolio: float, target: float = 0) -> dict:
        """
        计算仓位大小。
        返回 position_shares / position_pct / risk_amount / rr_ratio。
        """
        if entry <= stop or stop <= 0:
            return {"error": "止损价格必须低于入场价"}

        risk_per_share = entry - stop
        max_risk_amount = portfolio * self.max_single_risk_pct
        shares = int(max_risk_amount / risk_per_share)

        # 整手（A股100股为1手）
        shares = (shares // 100) * 100
        if shares <= 0:
            shares = 100

        position_value = shares * entry
        position_pct = position_value / portfolio * 100
        actual_risk = shares * risk_per_share
        actual_risk_pct = actual_risk / portfolio * 100

        # 盈亏比
        rr = round((target - entry) / risk_per_share, 1) if target > entry else 0

        return {
            "shares": shares,
            "position_value": round(position_value, 2),
            "position_pct": round(position_pct, 1),
            "risk_amount": round(actual_risk, 2),
            "risk_pct": round(actual_risk_pct, 2),
            "rr_ratio": rr,
            "meets_rr": rr >= self.min_rr_ratio,
            "t1_adjusted_entry": round(entry * (1 + self.t1_premium), 2),  # T+1买入溢价
        }

    def check_total_risk(self, positions: list, portfolio: float) -> dict:
        """检查所有持仓的总风险"""
        total_risk = sum(p.get("risk_amount", 0) for p in positions)
        total_risk_pct = total_risk / portfolio * 100 if portfolio > 0 else 0
        return {
            "total_risk": round(total_risk, 2),
            "total_risk_pct": round(total_risk_pct, 1),
            "within_limit": total_risk_pct <= self.max_total_risk_pct * 100,
            "remaining_budget": round((self.max_total_risk_pct * 100 - total_risk_pct), 1),
        }

    def validate_trade(self, entry: float, stop: float, target: float) -> dict:
        """快速验证交易参数是否符合风险规则"""
        issues = []
        if stop >= entry:
            issues.append("止损价格必须低于入场价")
        if target > 0:
            rr = (target - entry) / (entry - stop) if entry > stop else 0
            if rr < self.min_rr_ratio:
                issues.append(f"盈亏比{rr:.1f} < 最低要求{self.min_rr_ratio}")
        return {"valid": len(issues) == 0, "issues": issues}
