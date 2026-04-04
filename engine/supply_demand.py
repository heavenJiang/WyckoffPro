"""
engine/supply_demand.py — 六维度供需评分
-100（极端供应）~ +100（极端需求）
参考文档 4.2 节。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional
import numpy as np
import pandas as pd


@dataclass
class SDContext:
    """供需评分所需上下文"""
    df: pd.DataFrame               # K线数据（至少20根）
    up_vol: float = 0.0            # 近N日上涨波量均值
    down_vol: float = 0.0          # 近N日下跌波量均值
    channel_position: float = 0.0  # 在通道中的位置 (-1~1)
    north_flow_normalized: float = 0.0  # 北向资金归一化 (-100~100)
    weis_balance: float = 0.0      # 维斯波多空平衡 (-100~100)
    has_stopping_behavior: bool = False  # 是否有停止行为


class SupplyDemandScore:
    """
    六维度加权供需评分。
    维度：量价平衡、K线形态、通道位置、北向资金、维斯波、停止行为。
    """

    WEIGHTS = {
        "volume_price":  0.30,
        "bar_pattern":   0.20,
        "trend_position": 0.15,
        "smart_money":   0.15,
        "weis_wave":     0.10,
        "stopping":      0.10,
    }

    def calculate(self, df: pd.DataFrame, context: Optional[SDContext] = None) -> float:
        """
        计算供需评分。
        df: 最近N根K线（推荐20根以上）
        返回 -100 ~ +100 的浮点数（正=需求主导，负=供应主导）。
        """
        if df.empty or len(df) < 5:
            return 0.0

        ctx = context or self._build_context(df)

        scores = {
            "volume_price":  self._vp_balance(df) * 100,
            "bar_pattern":   self._bar_bull_ratio(df) * 200 - 100,
            "trend_position": ctx.channel_position * 100,
            "smart_money":   ctx.north_flow_normalized,
            "weis_wave":     ctx.weis_balance,
            "stopping":      self._stopping_score(df, ctx) * 100,
        }

        total = sum(scores[k] * self.WEIGHTS[k] for k in self.WEIGHTS)
        return round(max(-100.0, min(100.0, total)), 1)

    def get_breakdown(self, df: pd.DataFrame, context: Optional[SDContext] = None) -> Dict:
        """返回各维度明细"""
        ctx = context or self._build_context(df)
        scores = {
            "volume_price":  self._vp_balance(df) * 100,
            "bar_pattern":   self._bar_bull_ratio(df) * 200 - 100,
            "trend_position": ctx.channel_position * 100,
            "smart_money":   ctx.north_flow_normalized,
            "weis_wave":     ctx.weis_balance,
            "stopping":      self._stopping_score(df, ctx) * 100,
        }
        total = sum(scores[k] * self.WEIGHTS[k] for k in self.WEIGHTS)
        return {
            "scores": {k: round(v, 1) for k, v in scores.items()},
            "weights": self.WEIGHTS,
            "total": round(max(-100.0, min(100.0, total)), 1),
            "interpretation": self._interpret(total)
        }

    # ─── 各维度计算 ───

    def _vp_balance(self, df: pd.DataFrame, n: int = 20) -> float:
        """
        量价平衡：上涨日均量 vs 下跌日均量。
        返回 0(极端供应) ~ 1(极端需求)。
        """
        recent = df.tail(n)
        up = recent[recent["close"] >= recent["open"]]
        down = recent[recent["close"] < recent["open"]]
        avg_up = up["volume"].mean() if not up.empty else 0
        avg_down = down["volume"].mean() if not down.empty else 0
        ratio = avg_up / (avg_down + 1e-9)
        return min(1.0, max(0.0, ratio / 2.0))  # ratio=1 → 0.5, ratio=2 → 1.0

    def _bar_bull_ratio(self, df: pd.DataFrame, n: int = 20) -> float:
        """近N根K线中阳线比例"""
        recent = df.tail(n)
        if recent.empty:
            return 0.5
        return (recent["close"] >= recent["open"]).sum() / len(recent)

    def _stopping_score(self, df: pd.DataFrame, ctx: SDContext) -> float:
        """停止行为得分 (-1~1)"""
        if ctx.has_stopping_behavior:
            return 1.0
        # 简单启发：最后3根K线是否有大下影线（买入压力）
        last3 = df.tail(3)
        if last3.empty:
            return 0.0
        avg_lower_shadow = last3.apply(
            lambda r: (min(r["open"], r["close"]) - r["low"]) / (r["high"] - r["low"] + 1e-9),
            axis=1
        ).mean()
        return avg_lower_shadow * 2 - 1  # 0.5 shadow → 0.0

    def _build_context(self, df: pd.DataFrame) -> SDContext:
        """从K线数据构建基础上下文"""
        return SDContext(df=df, channel_position=0.0, north_flow_normalized=0.0, weis_balance=0.0)

    @staticmethod
    def _interpret(score: float) -> str:
        if score >= 60:
            return "极端需求主导"
        elif score >= 30:
            return "需求占优"
        elif score >= 10:
            return "轻微需求倾向"
        elif score >= -10:
            return "供需平衡"
        elif score >= -30:
            return "轻微供应倾向"
        elif score >= -60:
            return "供应占优"
        else:
            return "极端供应主导"
