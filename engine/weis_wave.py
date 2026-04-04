"""
engine/weis_wave.py — 维斯波（Weis Wave）分析
将连续同向 K 线聚合为波，累计波量，对比多空力量。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict
import pandas as pd
import numpy as np


@dataclass
class Wave:
    direction: str           # 'UP' or 'DOWN'
    volume: int = 0
    bars: int = 0
    price_change: float = 0.0
    start_price: float = 0.0
    end_price: float = 0.0
    start_date: str = ""
    end_date: str = ""


class WeisWave:
    """
    维斯波实现。
    连续同向K线聚合为一条波，计算波量，对比多空力量。
    参考文档 4.3 节。
    """

    def __init__(self, min_reversal_pct: float = 0.02):
        self.min_reversal_pct = min_reversal_pct

    def calculate(self, df: pd.DataFrame) -> List[Wave]:
        """
        计算全部波段。
        df: 包含 open/high/low/close/volume/trade_date 的 DataFrame。
        """
        if len(df) < 3:
            return []

        waves: List[Wave] = []
        current_wave = None

        for i, row in df.iterrows():
            is_up = row["close"] >= row["open"]
            direction = "UP" if is_up else "DOWN"

            if current_wave is None:
                current_wave = Wave(
                    direction=direction,
                    volume=int(row["volume"]),
                    bars=1,
                    price_change=row["close"] - row["open"],
                    start_price=row["open"],
                    end_price=row["close"],
                    start_date=str(row["trade_date"]),
                    end_date=str(row["trade_date"]),
                )
            elif direction == current_wave.direction:
                # 同向延续
                current_wave.volume += int(row["volume"])
                current_wave.bars += 1
                current_wave.end_price = row["close"]
                current_wave.end_date = str(row["trade_date"])
                current_wave.price_change = current_wave.end_price - current_wave.start_price
            else:
                # 方向改变：检查是否满足最小反转幅度
                reversal = abs(row["close"] - current_wave.end_price) / (current_wave.end_price + 1e-9)
                if reversal >= self.min_reversal_pct:
                    waves.append(current_wave)
                    current_wave = Wave(
                        direction=direction,
                        volume=int(row["volume"]),
                        bars=1,
                        price_change=row["close"] - row["open"],
                        start_price=row["open"],
                        end_price=row["close"],
                        start_date=str(row["trade_date"]),
                        end_date=str(row["trade_date"]),
                    )
                else:
                    # 未达反转阈值，归入当前波
                    current_wave.volume += int(row["volume"])
                    current_wave.bars += 1
                    current_wave.end_price = row["close"]
                    current_wave.end_date = str(row["trade_date"])

        if current_wave:
            waves.append(current_wave)

        return waves

    def analyze_balance(self, waves: List[Wave], recent_n: int = 6) -> float:
        """
        计算近N波的多空波量平衡。
        返回值 -100(完全空军) ~ +100(完全多军)。
        参考文档 4.3 节 analyze_balance()。
        """
        recent = waves[-recent_n:] if len(waves) >= recent_n else waves
        up_waves = [w for w in recent if w.direction == "UP"]
        down_waves = [w for w in recent if w.direction == "DOWN"]
        avg_up = sum(w.volume for w in up_waves) / max(len(up_waves), 1)
        avg_down = sum(w.volume for w in down_waves) / max(len(down_waves), 1)
        return round((avg_up - avg_down) / (avg_up + avg_down + 1e-9) * 100, 1)

    def get_wave_stats(self, waves: List[Wave]) -> Dict:
        """统计摘要"""
        if not waves:
            return {}
        up = [w for w in waves if w.direction == "UP"]
        down = [w for w in waves if w.direction == "DOWN"]
        return {
            "total_waves": len(waves),
            "up_waves": len(up),
            "down_waves": len(down),
            "avg_up_volume": round(sum(w.volume for w in up) / max(len(up), 1), 0),
            "avg_down_volume": round(sum(w.volume for w in down) / max(len(down), 1), 0),
            "balance": self.analyze_balance(waves),
            "last_direction": waves[-1].direction if waves else "N/A",
        }

    def waves_to_df(self, waves: List[Wave]) -> pd.DataFrame:
        """转为 DataFrame，方便图表显示"""
        return pd.DataFrame([
            {
                "direction": w.direction,
                "volume": w.volume,
                "bars": w.bars,
                "price_change": w.price_change,
                "start_price": w.start_price,
                "end_price": w.end_price,
                "start_date": w.start_date,
                "end_date": w.end_date,
            }
            for w in waves
        ])
