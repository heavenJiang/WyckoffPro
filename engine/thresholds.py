"""
engine/thresholds.py — 自适应阈值（基于百分位数）
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict


@dataclass
class Thresholds:
    """自适应阈值集合"""
    climax_vol_threshold: float = 0.0     # 放量高潮 成交量阈值（95th）
    climax_range_threshold: float = 0.0   # 放量高潮 振幅阈值（95th）
    spring_max_penetration: float = 0.0   # Spring 最大穿透（ATR*1.5）
    st_vol_ratio: float = 0.60            # ST 与 SC 成交量之比阈值
    low_vol_threshold: float = 0.0        # 低量测试阈值（20th）
    vdb_price_pct: float = 0.0            # VDB 价格变动（90th）
    vdb_vol_pct: float = 0.0              # VDB 成交量（90th）
    joc_vol_threshold: float = 0.0        # JOC 放量阈值（85th）
    atr_20: float = 0.0                   # 最新ATR(20)
    avg_vol_20: float = 0.0               # 近20日均量
    vol_20th: float = 0.0                 # 成交量20百分位（供需枯竭判断）
    vol_80th: float = 0.0                 # 成交量80百分位


class AdaptiveThresholds:
    """
    每只股票基于自身历史数据动态计算阈值，替代固定倍数。
    参考文档 2.3.1 节。
    """

    def __init__(self, lookback: int = 120):
        self.lookback = lookback

    def calc(self, stock_df: pd.DataFrame) -> Thresholds:
        """
        计算自适应阈值。
        stock_df: 完整K线 DataFrame（至少包含 volume, amplitude, atr_20, close）
        """
        df = stock_df.tail(self.lookback).copy()
        if df.empty:
            return Thresholds()

        vol = df["volume"]
        rng = df["amplitude"] if "amplitude" in df.columns else (
            (df["high"] - df["low"]) / df["close"].shift(1).replace(0, np.nan)
        )
        atr = df["atr_20"].iloc[-1] if "atr_20" in df.columns and not df["atr_20"].isna().all() else \
              (df["high"] - df["low"]).mean()

        return Thresholds(
            climax_vol_threshold=vol.quantile(0.95),
            climax_range_threshold=rng.quantile(0.95),
            spring_max_penetration=atr * 1.5,
            st_vol_ratio=0.60,
            low_vol_threshold=vol.quantile(0.20),
            vdb_price_pct=rng.quantile(0.90),
            vdb_vol_pct=vol.quantile(0.90),
            joc_vol_threshold=vol.quantile(0.85),
            atr_20=atr,
            avg_vol_20=vol.tail(20).mean(),
            vol_20th=vol.quantile(0.20),
            vol_80th=vol.quantile(0.80),
        )

    def to_dict(self, t: Thresholds) -> Dict:
        from dataclasses import asdict
        return asdict(t)
