"""
engine/signal_detector.py — 13种威科夫信号似然度检测
SC/AR/ST/Spring/SOS/SOW/UT/UTAD/JOC/LPSY/VDB/BC/PSY
参考文档 2.3.2 节。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Optional
import numpy as np
import pandas as pd
from engine.thresholds import Thresholds
from loguru import logger


SIGNAL_TYPES = ["SC", "AR", "ST", "Spring", "SOS", "SOW", "UT", "UTAD",
                "JOC", "LPSY", "VDB", "BC", "PSY"]


@dataclass
class Signal:
    signal_type: str
    likelihood: float        # 0.0 ~ 1.0
    strength: int = 0        # 1(弱) ~ 5(强)
    trigger_price: float = 0.0
    trigger_volume: int = 0
    rule_detail: str = ""
    phase_code: str = ""
    signal_date: str = ""

    def to_dict(self) -> dict:
        return {
            "signal_type": self.signal_type,
            "likelihood": round(self.likelihood, 3),
            "strength": self.strength,
            "trigger_price": self.trigger_price,
            "trigger_volume": self.trigger_volume,
            "rule_detail": self.rule_detail,
            "phase_code": self.phase_code,
            "signal_date": self.signal_date,
        }


class SignalDetector:
    """
    对每根K线计算13种信号的似然度分数(0-1)。
    基于自适应阈值，量价形态多维度加权。
    """

    def __init__(self, config: dict):
        self.min_likelihood = config.get("signals", {}).get("min_likelihood_to_record", 0.30)

    def scan(self, df: pd.DataFrame, thresholds: Thresholds,
             phase_code: str = "", context: dict = None) -> List[Signal]:
        """
        扫描当前K线（df末尾一根）的所有信号。
        context: 额外上下文（trend/low_60d/sc_low等）。
        """
        if df.empty or len(df) < 5:
            return []

        bar = df.iloc[-1]
        ctx = context or self._build_context(df)
        signals = []
        today = str(bar.get("trade_date", ""))

        detectors = [
            ("SC",     self._detect_sc),
            ("AR",     self._detect_ar),
            ("ST",     self._detect_st),
            ("Spring", self._detect_spring),
            ("SOS",    self._detect_sos),
            ("SOW",    self._detect_sow),
            ("UT",     self._detect_ut),
            ("UTAD",   self._detect_utad),
            ("JOC",    self._detect_joc),
            ("LPSY",   self._detect_lpsy),
            ("VDB",    self._detect_vdb),
            ("BC",     self._detect_bc),
            ("PSY",    self._detect_psy),
        ]

        for sig_type, fn in detectors:
            try:
                likelihood, detail = fn(bar, df, thresholds, ctx)
                if likelihood >= self.min_likelihood:
                    strength = min(5, max(1, int(likelihood * 5)))
                    signals.append(Signal(
                        signal_type=sig_type,
                        likelihood=round(likelihood, 3),
                        strength=strength,
                        trigger_price=float(bar.get("close", 0)),
                        trigger_volume=int(bar.get("volume", 0)),
                        rule_detail=detail,
                        phase_code=phase_code,
                        signal_date=today,
                    ))
            except Exception as e:
                logger.debug(f"检测 {sig_type} 失败: {e}")

        return signals

    # ─── 各信号检测函数 ───

    def _detect_sc(self, bar, df, t: Thresholds, ctx: dict) -> tuple[float, str]:
        """卖出高潮 (Selling Climax)"""
        scores = []
        # 维度1: 成交量异常程度 (0.30)
        vol_ratio = bar["volume"] / (t.climax_vol_threshold + 1e-9)
        scores.append((min(vol_ratio, 1.0), 0.30))
        # 维度2: 价格创新低 (0.25)
        low_60d = ctx.get("low_60d", bar["low"])
        s2 = 1.0 if bar["low"] <= low_60d else max(0, 1 - abs(low_60d - bar["low"]) / (t.atr_20 * 3 + 1e-9))
        scores.append((s2, 0.25))
        # 维度3: K线形态（长下影/大阴线） (0.20)
        rng = bar["high"] - bar["low"]
        body = abs(bar["close"] - bar["open"]) / (rng + 1e-9)
        shadow = (min(bar["open"], bar["close"]) - bar["low"]) / (rng + 1e-9)
        s3 = 0.5 + body * 0.3 + shadow * 0.2 if bar["close"] < bar["open"] else shadow * 0.8
        scores.append((s3, 0.20))
        # 维度4: 趋势背景（下跌中） (0.25)
        s4 = {"DOWN": 1.0, "SIDEWAYS": 0.3}.get(ctx.get("trend", ""), 0.0)
        scores.append((s4, 0.25))

        likelihood = sum(s * w for s, w in scores)
        detail = f"量ratio={vol_ratio:.2f}, 趋势={ctx.get('trend','')}, 低创={bar['low'] <= low_60d}"
        return likelihood, detail

    def _detect_ar(self, bar, df, t: Thresholds, ctx: dict) -> tuple[float, str]:
        """自动反弹 (Automatic Rally)"""
        # AR: SC后快速反弹，缩量，幅度合理
        if not ctx.get("has_sc", False):
            return 0.0, "无SC"
        recent_sc = ctx.get("sc_date_idx", len(df) - 1)
        bars_since_sc = len(df) - 1 - recent_sc
        if bars_since_sc > 15 or bars_since_sc < 1:
            return 0.1, "SC距离不合适"

        sc_bar = df.iloc[recent_sc]
        vol_ratio = bar["volume"] / (sc_bar["volume"] + 1e-9)
        is_up = bar["close"] > bar["open"]
        price_change = (bar["close"] - sc_bar["low"]) / (sc_bar["low"] + 1e-9)

        likelihood = (
            (0.5 if is_up else 0.0) * 0.35 +
            (min(1.0, max(0, 1 - vol_ratio)) * 0.35) +  # 缩量
            (min(1.0, price_change / 0.05) * 0.30)  # 反弹幅度
        )
        return likelihood, f"SC后{bars_since_sc}根，量比={vol_ratio:.2f}"

    def _detect_st(self, bar, df, t: Thresholds, ctx: dict) -> tuple[float, str]:
        """二次测试 (Secondary Test)"""
        if not ctx.get("has_sc", False):
            return 0.0, "无SC"
        sc_low = ctx.get("sc_low", bar["low"])
        penetration = (sc_low - bar["low"]) / (t.atr_20 + 1e-9)
        vol_vs_sc = bar["volume"] / (ctx.get("sc_volume", bar["volume"]) + 1e-9)

        # ST应: 测试SC低点但不明显新低 且 缩量
        s1 = max(0, 1 - abs(penetration) * 0.5)  # 越接近SC低点越好
        s2 = min(1.0, max(0, t.st_vol_ratio * 2 - vol_vs_sc))  # 缩量（<0.6倍最理想）
        s3 = 1.0 if penetration < 2.0 else max(0, 1 - (penetration - 2) * 0.3)  # 不深穿

        likelihood = s1 * 0.40 + s2 * 0.35 + s3 * 0.25
        return likelihood, f"测试深度={penetration:.2f}ATR, 量比={vol_vs_sc:.2f}"

    def _detect_spring(self, bar, df, t: Thresholds, ctx: dict) -> tuple[float, str]:
        """弹簧 (Spring) / 震仓"""
        tr_lower = ctx.get("tr_lower", 0)
        if tr_lower <= 0:
            return 0.0, "无TR区间"

        penetration = (tr_lower - bar["low"]) / (t.atr_20 + 1e-9)
        close_recovery = bar["close"] > tr_lower
        vol_ratio = bar["volume"] / (t.avg_vol_20 + 1e-9)

        # Spring: 小幅穿透TR下轨 + 当日或次日收回支撑上方 + 成交量收缩
        s1 = 1.0 if 0 < penetration <= 1.5 else max(0, 1 - abs(penetration - 0.75))
        s2 = 1.0 if close_recovery else 0.3
        s3 = min(1.0, max(0, 1.5 - vol_ratio))  # 缩量

        likelihood = s1 * 0.40 + s2 * 0.35 + s3 * 0.25
        detail = f"穿透={penetration:.2f}ATR, 收回={close_recovery}, 量={vol_ratio:.2f}倍均"
        return likelihood, detail

    def _detect_sos(self, bar, df, t: Thresholds, ctx: dict) -> tuple[float, str]:
        """力量信号 (Sign of Strength)"""
        tr_upper = ctx.get("tr_upper", float("inf"))
        vol_ratio = bar["volume"] / (t.avg_vol_20 + 1e-9)
        is_up = bar["close"] > bar["open"]
        breaks_resistance = bar["close"] > tr_upper

        s1 = 1.0 if is_up else 0.0
        s2 = min(1.0, vol_ratio / 1.5)  # 放量
        s3 = 1.0 if breaks_resistance else max(0, bar["close"] / (tr_upper + 1e-9) - 0.95) * 20

        likelihood = s1 * 0.35 + s2 * 0.40 + s3 * 0.25
        return likelihood, f"突破阻力={breaks_resistance}, 量={vol_ratio:.2f}倍"

    def _detect_sow(self, bar, df, t: Thresholds, ctx: dict) -> tuple[float, str]:
        """弱点信号 (Sign of Weakness)"""
        tr_lower = ctx.get("tr_lower", 0)
        vol_ratio = bar["volume"] / (t.avg_vol_20 + 1e-9)
        is_down = bar["close"] < bar["open"]
        breaks_support = tr_lower > 0 and bar["close"] < tr_lower

        s1 = 1.0 if is_down else 0.0
        s2 = min(1.0, vol_ratio / 1.5)  # 放量下跌
        s3 = 1.0 if breaks_support else 0.3

        likelihood = s1 * 0.35 + s2 * 0.40 + s3 * 0.25
        return likelihood, f"跌破支撑={breaks_support}, 量={vol_ratio:.2f}倍"

    def _detect_ut(self, bar, df, t: Thresholds, ctx: dict) -> tuple[float, str]:
        """向上试探 (Upthrust)"""
        tr_upper = ctx.get("tr_upper", 0)
        if tr_upper <= 0:
            return 0.0, "无TR区间"

        penetration = (bar["high"] - tr_upper) / (t.atr_20 + 1e-9)
        close_below = bar["close"] < tr_upper
        vol_ratio = bar["volume"] / (t.avg_vol_20 + 1e-9)

        # UT: 突破TR上轨但收盘回到TR内
        s1 = 1.0 if 0 < penetration < 2.0 else max(0, 1 - abs(penetration - 1.0) * 0.5)
        s2 = 1.0 if close_below else 0.0
        s3 = min(1.0, vol_ratio / 1.2)  # 较大成交量

        likelihood = s1 * 0.35 + s2 * 0.40 + s3 * 0.25
        return likelihood, f"穿透={penetration:.2f}ATR, 收回={close_below}"

    def _detect_utad(self, bar, df, t: Thresholds, ctx: dict) -> tuple[float, str]:
        """吸筹区末期试探 (UTAD)"""
        # UTAD: 在吸筹后期出现，类似UT但量价更明显
        tr_upper = ctx.get("tr_upper", 0)
        if tr_upper <= 0:
            return 0.0, "无TR区间"
        phase_code = ctx.get("phase_code", "")
        if "ACC" not in phase_code:
            return 0.0, "非吸筹阶段"

        likelihood, detail = self._detect_ut(bar, df, t, ctx)
        # UTAD需要更强的放量
        vol_ratio = bar["volume"] / (t.avg_vol_20 + 1e-9)
        likelihood = likelihood * 0.7 + min(1.0, vol_ratio / 2.0) * 0.3
        return likelihood, f"UTAD（吸筹末期）: {detail}"

    def _detect_joc(self, bar, df, t: Thresholds, ctx: dict) -> tuple[float, str]:
        """跳出冰点 (Jump Over Creek / JOC)"""
        creek = ctx.get("creek_line", 0)
        if creek <= 0:
            return 0.0, "无Creek线"

        breaks_creek = bar["close"] > creek
        vol_ratio = bar["volume"] / (t.joc_vol_threshold + 1e-9)
        price_gap = (bar["close"] - creek) / (t.atr_20 + 1e-9)

        s1 = 1.0 if breaks_creek else max(0, 1 - (creek - bar["close"]) / t.atr_20)
        s2 = min(1.0, vol_ratio)  # 大量
        s3 = min(1.0, price_gap / 0.5)

        likelihood = s1 * 0.45 + s2 * 0.35 + s3 * 0.20
        return likelihood, f"突破Creek={breaks_creek}, 量={vol_ratio:.2f}x阈值"

    def _detect_lpsy(self, bar, df, t: Thresholds, ctx: dict) -> tuple[float, str]:
        """最后供应点 (Last Point of Supply)"""
        tr_upper = ctx.get("tr_upper", 0)
        if tr_upper <= 0:
            return 0.0, "无TR区间"

        rally_to_resistance = abs(bar["close"] - tr_upper) / (t.atr_20 + 1e-9) < 1.0
        is_weak = bar["close"] < bar.get("prev_close", bar["close"])
        vol_ratio = bar["volume"] / (t.avg_vol_20 + 1e-9)

        s1 = 1.0 if rally_to_resistance else 0.3
        s2 = 1.0 if is_weak else 0.2
        s3 = min(1.0, max(0, 1.5 - vol_ratio))  # 缩量上涨=LPSY

        likelihood = s1 * 0.40 + s2 * 0.30 + s3 * 0.30
        phase_code = ctx.get("phase_code", "")
        if "DIS" not in phase_code:
            likelihood *= 0.5  # 派发阶段才常见LPSY
        return likelihood, f"反弹至阻力={rally_to_resistance}, 量={vol_ratio:.2f}倍"

    def _detect_vdb(self, bar, df, t: Thresholds, ctx: dict) -> tuple[float, str]:
        """突破量 (Volume Dry-up Breakout / VDB)"""
        # VDB: 缩量测试支撑成功
        tr_lower = ctx.get("tr_lower", 0)
        vol_ratio = bar["volume"] / (t.avg_vol_20 + 1e-9)
        holds_support = tr_lower <= 0 or bar["close"] > tr_lower

        s1 = min(1.0, max(0, t.st_vol_ratio - vol_ratio + 0.5))  # 极低量
        s2 = 1.0 if holds_support else 0.2
        s3 = 1.0 if bar["close"] > bar["open"] else 0.4

        likelihood = s1 * 0.45 + s2 * 0.35 + s3 * 0.20
        return likelihood, f"量={vol_ratio:.2f}倍均量, 守支撑={holds_support}"

    def _detect_bc(self, bar, df, t: Thresholds, ctx: dict) -> tuple[float, str]:
        """买入高潮 (Buying Climax)"""
        vol_ratio = bar["volume"] / (t.climax_vol_threshold + 1e-9)
        high_60d = df["high"].tail(60).max()
        new_high = bar["high"] >= high_60d * 0.99
        amp_ratio = (bar["high"] - bar["low"]) / (t.climax_range_threshold + 1e-9)

        s1 = min(1.0, vol_ratio)
        s2 = 1.0 if new_high else 0.3
        s3 = min(1.0, amp_ratio)
        s4 = {"UP": 1.0, "SIDEWAYS": 0.3}.get(ctx.get("trend", ""), 0.0)

        likelihood = s1 * 0.30 + s2 * 0.25 + s3 * 0.20 + s4 * 0.25
        return likelihood, f"量ratio={vol_ratio:.2f}, 创高={new_high}"

    def _detect_psy(self, bar, df, t: Thresholds, ctx: dict) -> tuple[float, str]:
        """初步供给 (Preliminary Supply)"""
        # PSY: 上涨途中出现大量高潮，可能是供应开始
        vol_ratio = bar["volume"] / (t.climax_vol_threshold + 1e-9)
        is_up = bar["close"] > bar["open"]
        trend = ctx.get("trend", "")

        s1 = min(1.0, vol_ratio)
        s2 = 1.0 if is_up else 0.2
        s3 = 1.0 if trend == "UP" else 0.3

        likelihood = s1 * 0.35 + s2 * 0.30 + s3 * 0.35
        likelihood *= 0.7  # PSY相对稀有，信号弱化
        return likelihood, f"初步供给，量={vol_ratio:.2f}x高潮阈值"

    # ─── 上下文构建 ───

    def _build_context(self, df: pd.DataFrame) -> dict:
        """从K线序列提取默认上下文"""
        ctx = {}
        if df.empty:
            return ctx
        close = df["close"]
        volume = df["volume"]

        # 趋势判断（简单：近20日均线位置）
        ma20 = close.rolling(20, min_periods=5).mean()
        if len(ma20) > 0 and not pd.isna(ma20.iloc[-1]):
            if close.iloc[-1] > ma20.iloc[-1] * 1.02:
                ctx["trend"] = "UP"
            elif close.iloc[-1] < ma20.iloc[-1] * 0.98:
                ctx["trend"] = "DOWN"
            else:
                ctx["trend"] = "SIDEWAYS"

        ctx["low_60d"] = df["low"].tail(60).min()
        ctx["high_60d"] = df["high"].tail(60).max()

        return ctx
