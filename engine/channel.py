"""
engine/channel.py — 趋势通道 + 超买超卖线 + Creek/Ice 关键价位
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, Optional
import numpy as np
import pandas as pd


@dataclass
class ChannelLevels:
    upper: float = 0.0       # 通道上轨（超买线）
    lower: float = 0.0       # 通道下轨（超卖线）
    mid: float = 0.0         # 通道中线
    creek_line: float = 0.0  # Creek线（TR区阻力）
    ice_line: float = 0.0    # Ice线（TR区支撑）
    support_1: float = 0.0   # 主要支撑1
    support_2: float = 0.0   # 主要支撑2
    resistance_1: float = 0.0
    resistance_2: float = 0.0
    channel_position: float = 0.0  # 当前价在通道中的位置 (-1~1)


class ChannelAnalyzer:
    """趋势通道和关键价位分析"""

    def analyze(self, df: pd.DataFrame, tr_upper: float = 0, tr_lower: float = 0) -> ChannelLevels:
        """
        计算通道和关键价位。
        使用线性回归通道 + 分位数支撑/阻力。
        """
        if df.empty or len(df) < 20:
            return ChannelLevels()

        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        n = len(close)
        x = np.arange(n)

        # 线性回归中线
        coeffs = np.polyfit(x, close, 1)
        mid_line = np.poly1d(coeffs)(x)

        # 通道宽度（偏差）
        deviations = close - mid_line
        std = deviations.std()

        current_mid = mid_line[-1]
        upper = current_mid + 2 * std
        lower = current_mid - 2 * std

        # 当前价在通道中的位置
        current_close = float(close[-1])
        channel_range = upper - lower
        position = ((current_close - lower) / channel_range * 2 - 1) if channel_range > 0 else 0
        position = max(-1.0, min(1.0, position))

        # 支撑/阻力（近60日高低点的分位数）
        period = min(n, 60)
        recent_high = high[-period:]
        recent_low = low[-period:]

        resistance_1 = np.percentile(recent_high, 85)
        resistance_2 = np.percentile(recent_high, 95)
        support_1 = np.percentile(recent_low, 15)
        support_2 = np.percentile(recent_low, 5)

        # Creek 和 Ice
        creek = tr_upper * 0.97 if tr_upper > 0 else resistance_1 * 0.97
        ice = tr_lower * 1.03 if tr_lower > 0 else support_1 * 1.03

        return ChannelLevels(
            upper=round(upper, 2),
            lower=round(lower, 2),
            mid=round(current_mid, 2),
            creek_line=round(creek, 2),
            ice_line=round(ice, 2),
            support_1=round(support_1, 2),
            support_2=round(support_2, 2),
            resistance_1=round(resistance_1, 2),
            resistance_2=round(resistance_2, 2),
            channel_position=round(position, 3),
        )

    def is_overbought(self, levels: ChannelLevels, current_price: float) -> bool:
        return current_price >= levels.upper * 0.98

    def is_oversold(self, levels: ChannelLevels, current_price: float) -> bool:
        return current_price <= levels.lower * 1.02

    def get_nearest_support(self, levels: ChannelLevels, current_price: float) -> float:
        supports = [s for s in [levels.support_1, levels.support_2, levels.ice_line, levels.lower] if s > 0 and s < current_price]
        return max(supports) if supports else levels.lower

    def get_nearest_resistance(self, levels: ChannelLevels, current_price: float) -> float:
        resistances = [r for r in [levels.resistance_1, levels.resistance_2, levels.creek_line, levels.upper] if r > current_price]
        return min(resistances) if resistances else levels.upper
