"""
engine/pnf_chart.py — 点数图（Point & Figure Chart）目标价计算
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import pandas as pd
import numpy as np


@dataclass
class PnFBox:
    value: float
    direction: str  # 'X' or 'O'
    date: str


@dataclass
class PnFChart:
    boxes: List[PnFBox] = field(default_factory=list)
    box_size: float = 0.0
    reversal_boxes: int = 3
    columns: List[List[PnFBox]] = field(default_factory=list)

    # 计算得到的目标价
    count_target: float = 0.0      # 横向计数目标
    projection_target: float = 0.0 # 垂直测量目标
    base_low: float = 0.0          # 基础低点（用于横向计数）
    base_width: int = 0            # 横向宽度（格数）


class PnFAnalyzer:
    """
    点数图分析。
    - 自动计算盒子大小（ATR比例）
    - 三格反转标准
    - 横向计数（吸筹因果）
    - 垂直测量（趋势延伸目标）
    """

    def __init__(self, reversal_boxes: int = 3):
        self.reversal_boxes = reversal_boxes

    def build(self, df: pd.DataFrame, box_size: float = None) -> PnFChart:
        """从K线数据构建点数图"""
        if df.empty or len(df) < 5:
            return PnFChart()

        # 自动确定盒大小
        if box_size is None:
            atr = df["atr_20"].iloc[-1] if "atr_20" in df.columns else (df["high"] - df["low"]).mean()
            box_size = max(atr * 0.5, df["close"].iloc[-1] * 0.01)  # min 1%
            box_size = round(box_size, 2)

        chart = PnFChart(box_size=box_size, reversal_boxes=self.reversal_boxes)
        current_col: List[PnFBox] = []
        current_dir = "X"
        current_price = df["close"].iloc[0]

        for _, row in df.iterrows():
            date = str(row["trade_date"])
            high = row["high"]
            low = row["low"]

            if current_dir == "X":
                # 检查能否继续向上
                boxes_up = int((high - current_price) / box_size)
                if boxes_up > 0:
                    for i in range(boxes_up):
                        current_price += box_size
                        current_col.append(PnFBox(current_price, "X", date))
                # 检查是否需要反转
                elif int((current_price - low) / box_size) >= self.reversal_boxes:
                    chart.columns.append(current_col)
                    current_col = []
                    current_dir = "O"
                    boxes_down = int((current_price - low) / box_size)
                    for i in range(boxes_down):
                        current_price -= box_size
                        current_col.append(PnFBox(current_price, "O", date))
            else:
                # 检查能否继续向下
                boxes_down = int((current_price - low) / box_size)
                if boxes_down > 0:
                    for i in range(boxes_down):
                        current_price -= box_size
                        current_col.append(PnFBox(current_price, "O", date))
                # 检查是否需要反转
                elif int((high - current_price) / box_size) >= self.reversal_boxes:
                    chart.columns.append(current_col)
                    current_col = []
                    current_dir = "X"
                    boxes_up = int((high - current_price) / box_size)
                    for i in range(boxes_up):
                        current_price += box_size
                        current_col.append(PnFBox(current_price, "X", date))

        if current_col:
            chart.columns.append(current_col)

        # 计算目标价
        self._calc_targets(chart, df)
        return chart

    def _calc_targets(self, chart: PnFChart, df: pd.DataFrame):
        """计算点数图目标价"""
        if not chart.columns:
            return

        # 横向计数：在TR区间内数格数
        # 找最近的底部区域（O列集中区）
        o_columns = [col for col in chart.columns if col and col[0].direction == "O"]
        if o_columns:
            # 取最低点作为基础
            all_lows = [min(b.value for b in col) for col in o_columns[-10:]]
            base_low = min(all_lows)
            # 横向宽度（近期O列数量）
            base_width = len(o_columns[-10:])
            chart.base_low = base_low
            chart.base_width = base_width
            # 目标：底部 + (宽度 × 反转格数 × 盒大小)
            chart.count_target = base_low + base_width * self.reversal_boxes * chart.box_size

        # 垂直测量：最近一列的高度 × 2
        if chart.columns:
            last_col = chart.columns[-1]
            if last_col:
                low_val = min(b.value for b in last_col)
                high_val = max(b.value for b in last_col)
                col_height = high_val - low_val
                if last_col[0].direction == "X":
                    chart.projection_target = high_val + col_height
                else:
                    chart.projection_target = low_val - col_height

    def get_targets(self, chart: PnFChart) -> dict:
        """获取目标价摘要"""
        return {
            "count_target": round(chart.count_target, 2),
            "projection_target": round(chart.projection_target, 2),
            "box_size": chart.box_size,
            "base_low": round(chart.base_low, 2),
            "base_width": chart.base_width,
        }
