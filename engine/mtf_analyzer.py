"""
engine/mtf_analyzer.py — 多时间框架（MTF）分析
周线/日线/60分钟线阶段共振分析。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional
from loguru import logger


@dataclass
class MTFAlignment:
    """多时间框架对齐分析结果"""
    weekly_phase: str = "UNKNOWN"
    weekly_conf: float = 0.0
    daily_phase: str = "UNKNOWN"
    daily_conf: float = 0.0
    intra_phase: str = "UNKNOWN"
    intra_conf: float = 0.0
    alignment_score: float = 0.0     # 0-100，三框共振得分
    alignment_type: str = "NEUTRAL"  # BULLISH/BEARISH/NEUTRAL/CONFLICT
    contradiction: str = ""          # 矛盾描述


class MTFAnalyzer:
    """
    多时间框架分析器。
    - 分析周线/日线/分钟线的阶段是否共振
    - 共振分=最终综合评分的一个维度
    """

    # 阶段方向映射
    PHASE_DIRECTION = {
        "MKD": -2, "DIS-A": -1, "DIS-B": -1, "DIS-C": -2, "DIS-D": -2,
        "TR_UNDETERMINED": 0,
        "ACC-A": 1, "ACC-B": 1, "ACC-C": 1, "ACC-D": 2, "ACC-E": 2,
        "MKU": 2, "UNKNOWN": 0,
    }

    def analyze(self, weekly_phase: str, weekly_conf: float,
                daily_phase: str, daily_conf: float,
                intra_phase: str = "UNKNOWN", intra_conf: float = 0.0) -> MTFAlignment:
        """分析多时间框架对齐情况"""
        w_dir = self.PHASE_DIRECTION.get(weekly_phase, 0)
        d_dir = self.PHASE_DIRECTION.get(daily_phase, 0)
        i_dir = self.PHASE_DIRECTION.get(intra_phase, 0)

        # 加权方向（周线权重最高）
        weighted = w_dir * 0.50 + d_dir * 0.35 + i_dir * 0.15

        # 对齐类型
        if weighted >= 1.5:
            alignment_type = "BULLISH"
        elif weighted <= -1.5:
            alignment_type = "BEARISH"
        elif abs(weighted) < 0.3:
            alignment_type = "NEUTRAL"
        else:
            alignment_type = "WEAK_BULLISH" if weighted > 0 else "WEAK_BEARISH"

        # 冲突检测
        contradiction = ""
        if w_dir < 0 and d_dir > 0:
            contradiction = f"⚠️ 周线下跌（{weekly_phase}）但日线看涨（{daily_phase}），可能是反弹"
        elif w_dir > 0 and d_dir < 0:
            contradiction = f"⚠️ 周线看涨（{weekly_phase}）但日线弱势（{daily_phase}），可能是调整"
        elif w_dir > 0 and d_dir > 0 and i_dir < 0:
            contradiction = f"⚠️ 日线以上多头但短线（{intra_phase}）弱势，注意入场时机"

        # 对齐分（0-100）
        dirs = [w_dir, d_dir, i_dir]
        max_diff = max(abs(a - b) for a in dirs for b in dirs)
        alignment_score = max(0.0, 100.0 - max_diff * 25) * min(weekly_conf, daily_conf)

        # MTF分 (用于综合评分)
        mtf_score = round(alignment_score * 0.15, 1)  # 权重15%

        return MTFAlignment(
            weekly_phase=weekly_phase,
            weekly_conf=weekly_conf,
            daily_phase=daily_phase,
            daily_conf=daily_conf,
            intra_phase=intra_phase,
            intra_conf=intra_conf,
            alignment_score=round(alignment_score, 1),
            alignment_type=alignment_type,
            contradiction=contradiction,
        )

    def calc_mtf_score(self, alignment: MTFAlignment) -> float:
        """返回用于综合评分的MTF分（0-15）"""
        return round(alignment.alignment_score / 100 * 15, 1)

    def get_summary(self, alignment: MTFAlignment) -> str:
        """生成可读摘要"""
        lines = [
            f"周线: {alignment.weekly_phase}({alignment.weekly_conf:.0%})",
            f"日线: {alignment.daily_phase}({alignment.daily_conf:.0%})",
            f"对齐: {alignment.alignment_type}（得分{alignment.alignment_score:.0f}/100）",
        ]
        if alignment.contradiction:
            lines.append(alignment.contradiction)
        return " | ".join(lines)
