"""
engine/phase_fsm.py — 威科夫阶段有限状态机（含V3.1紧急反转路径）
完整FSM: MKD → ACC-A → ACC-B → ACC-C → ACC-D → ACC-E → MKU
         MKU → DIS-A → DIS-B → DIS-C → DIS-D → MKD
         + TR_UNDETERMINED 中性待判定状态
         + 紧急反转路径（反面积分≥71触发）
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import pandas as pd
from loguru import logger


# ─── 阶段定义 ───
PHASES = {
    # 下跌趋势
    "MKD":            {"name": "下跌趋势", "color": "#e74c3c", "hypothesis": None},
    # 吸筹阶段
    "ACC-A":          {"name": "吸筹阶段A（停止行为）", "color": "#e67e22", "hypothesis": "ACCUMULATION"},
    "ACC-B":          {"name": "吸筹阶段B（建立原因）", "color": "#f39c12", "hypothesis": "ACCUMULATION"},
    "ACC-C":          {"name": "吸筹阶段C（测试）", "color": "#f1c40f", "hypothesis": "ACCUMULATION"},
    "ACC-D":          {"name": "吸筹阶段D（需求主导）", "color": "#2ecc71", "hypothesis": "ACCUMULATION"},
    "ACC-E":          {"name": "吸筹阶段E（上涨中）", "color": "#27ae60", "hypothesis": "ACCUMULATION"},
    # 上涨趋势
    "MKU":            {"name": "上涨趋势", "color": "#00bcd4", "hypothesis": None},
    # 派发阶段
    "DIS-A":          {"name": "派发阶段A（停止行为）", "color": "#3498db", "hypothesis": "DISTRIBUTION"},
    "DIS-B":          {"name": "派发阶段B（建立供应）", "color": "#9b59b6", "hypothesis": "DISTRIBUTION"},
    "DIS-C":          {"name": "派发阶段C（UTAD）", "color": "#8e44ad", "hypothesis": "DISTRIBUTION"},
    "DIS-D":          {"name": "派发阶段D（弱点明显）", "color": "#c0392b", "hypothesis": "DISTRIBUTION"},
    # 中性未定
    "TR_UNDETERMINED": {"name": "震荡区方向未定", "color": "#95a5a6", "hypothesis": None},
    "UNKNOWN":        {"name": "未知/未分析", "color": "#7f8c8d", "hypothesis": None},
}

# ─── 正常状态转移图 ───
TRANSITIONS = {
    "MKD":          {"next": ["ACC-A"], "prev": ["DIS-D", "TR_UNDETERMINED"]},
    "ACC-A":        {"next": ["ACC-B"], "prev": ["MKD"]},
    "ACC-B":        {"next": ["ACC-C"], "prev": ["ACC-A", "ACC-C"]},
    "ACC-C":        {"next": ["ACC-D"], "prev": ["ACC-B"]},
    "ACC-D":        {"next": ["ACC-E", "MKU"], "prev": ["ACC-C"]},
    "ACC-E":        {"next": ["MKU"], "prev": ["ACC-D"]},
    "MKU":          {"next": ["DIS-A"], "prev": ["ACC-E", "ACC-D"]},
    "DIS-A":        {"next": ["DIS-B"], "prev": ["MKU"]},
    "DIS-B":        {"next": ["DIS-C"], "prev": ["DIS-A", "DIS-C"]},
    "DIS-C":        {"next": ["DIS-D"], "prev": ["DIS-B"]},
    "DIS-D":        {"next": ["MKD"], "prev": ["DIS-C"]},
    "TR_UNDETERMINED": {"next": ["ACC-A", "DIS-A"], "prev": []},
    "UNKNOWN":      {"next": [], "prev": []},
}

# ─── 各阶段判定条件 ───
ACC_A_SIGNALS = {"SC", "AR"}
ACC_B_SIGNALS = {"ST", "VDB"}
ACC_C_SIGNALS = {"Spring", "SOS"}
ACC_D_SIGNALS = {"SOS", "JOC"}
DIS_A_SIGNALS = {"BC", "AR"}
DIS_B_SIGNALS = {"UT", "SOW", "LPSY"}
DIS_C_SIGNALS = {"UTAD", "SOW"}
DIS_D_SIGNALS = {"SOW", "BreakIce"}


@dataclass
class PhaseState:
    stock_code: str
    phase_code: str = "UNKNOWN"
    confidence: float = 0.0
    start_date: str = ""
    tr_upper: float = 0.0
    tr_lower: float = 0.0
    ice_line: float = 0.0
    creek_line: float = 0.0
    timeframe: str = "daily"
    evidence_chain: List[str] = field(default_factory=list)
    duration_days: int = 0


class PhaseFSM:
    """
    威科夫阶段有限状态机。
    - 正常状态转移（信号驱动）
    - 紧急反转路径（反面积分≥71触发）
    - 回退路径（ACC-C → ACC-B）
    - TR_UNDETERMINED 中性等待
    """

    def __init__(self, config: dict, storage):
        self.config = config
        self.storage = storage
        self._states: Dict[str, PhaseState] = {}
        self.min_evidence = config.get("phase_fsm", {}).get("min_evidence_for_transition", 2)

    def get_current_phase(self, stock_code: str, timeframe: str = "daily") -> PhaseState:
        """获取当前阶段（优先内存，fallback DB）"""
        key = f"{stock_code}_{timeframe}"
        if key not in self._states:
            db = self.storage.get_current_phase(stock_code, timeframe)
            if db:
                self._states[key] = PhaseState(
                    stock_code=stock_code,
                    phase_code=db["phase_code"],
                    confidence=db.get("confidence", 0.5),
                    start_date=db.get("start_date", ""),
                    tr_upper=db.get("tr_upper", 0),
                    tr_lower=db.get("tr_lower", 0),
                    ice_line=db.get("ice_line", 0),
                    creek_line=db.get("creek_line", 0),
                    timeframe=timeframe,
                )
            else:
                self._states[key] = PhaseState(stock_code=stock_code, timeframe=timeframe)
        return self._states[key]

    def process_bar(self, stock_code: str, df: pd.DataFrame,
                    signals: list, ce_result: dict,
                    timeframe: str = "daily") -> PhaseState:
        """
        处理新K线，更新阶段状态。
        signals: signal_detector.scan() 返回的信号列表
        ce_result: counter_evidence.update() 返回的结果
        """
        state = self.get_current_phase(stock_code, timeframe)
        bar = df.iloc[-1]
        today = str(bar.get("trade_date", datetime.now().date()))
        signal_types = {s.signal_type if hasattr(s, "signal_type") else s.get("signal_type", "") for s in signals}

        # 1. 紧急反转检查（优先于正常转移）
        if ce_result.get("reversal_triggered"):
            new_phase = ce_result["reversal_target"]
            reasoning = ce_result.get("reversal_reasoning", "紧急反转")
            logger.warning(f"[{stock_code}] 🚨 紧急反转: {state.phase_code} → {new_phase}")
            self._transition(state, new_phase, today, confidence=0.7,
                             reason=f"紧急反转: {reasoning}", df=df)
            self._save(state)
            return state

        # 2. 正常状态转移检查
        new_phase, confidence, reason = self._check_normal_transition(
            state, signal_types, df, bar
        )
        if new_phase:
            self._transition(state, new_phase, today, confidence, reason, df)

        # 3. 更新TR区间和持续天数
        self._update_tr(state, df)
        state.duration_days = self._calc_duration(state.start_date, today)

        self._save(state)
        return state

    def force_transition(self, stock_code: str, new_phase: str, reason: str = "",
                         timeframe: str = "daily") -> PhaseState:
        """强制状态转移（手动触发或AI证伪驱动）"""
        state = self.get_current_phase(stock_code, timeframe)
        today = datetime.now().date().isoformat()
        self._transition(state, new_phase, today, confidence=0.6, reason=reason)
        self._save(state)
        return state

    def adjust_confidence(self, stock_code: str, delta: float, timeframe: str = "daily"):
        """微调阶段置信度（AI证伪结果调整）"""
        state = self.get_current_phase(stock_code, timeframe)
        state.confidence = max(0.0, min(1.0, state.confidence + delta / 100.0))
        self._save(state)

    # ─── 内部方法 ───

    def _check_normal_transition(
        self, state: PhaseState, signal_types: set, df: pd.DataFrame, bar: pd.Series
    ) -> Tuple[Optional[str], float, str]:
        """检查正常状态转移条件"""
        phase = state.phase_code
        close = float(bar.get("close", 0))

        if phase == "UNKNOWN":
            return self._detect_initial_phase(signal_types, df)

        elif phase == "MKD":
            if ACC_A_SIGNALS & signal_types:
                return "ACC-A", 0.6, f"出现停止信号: {ACC_A_SIGNALS & signal_types}"
            # 也可能直接进派发 (难以判断，从UNKNOWN开始)

        elif phase == "ACC-A":
            if ACC_B_SIGNALS & signal_types and state.duration_days >= 5:
                return "ACC-B", 0.65, f"出现ST/VDB，进入吸筹B阶段: {signal_types}"

        elif phase == "ACC-B":
            if "Spring" in signal_types:
                return "ACC-C", 0.70, "出现Spring，进入吸筹C阶段"
            if "SOW" in signal_types:
                return "ACC-B", 0.65, "SOW出现，吸筹B回退测试（保持）"

        elif phase == "ACC-C":
            if "SOS" in signal_types and state.tr_upper > 0 and close > state.tr_upper * 0.98:
                return "ACC-D", 0.75, "Spring后SOS出现，进入吸筹D阶段"
            # 回退到ACC-B（正常）
            if "SOW" in signal_types:
                return "ACC-B", 0.60, "SOW出现，Spring可能未成功，回退ACC-B"

        elif phase == "ACC-D":
            if "JOC" in signal_types:
                return "ACC-E", 0.80, "JOC突破Creek，进入吸筹E阶段"
            if close > state.tr_upper * 1.05 and state.duration_days >= 10:
                return "MKU", 0.70, "明显突破TR上轨，进入上涨趋势"

        elif phase == "ACC-E":
            if close > state.tr_upper * 1.1:
                return "MKU", 0.80, "价格明显脱离TR，确认上涨趋势"

        elif phase == "MKU":
            if DIS_A_SIGNALS & signal_types:
                return "DIS-A", 0.60, f"出现BC等停止行为: {DIS_A_SIGNALS & signal_types}"

        elif phase == "DIS-A":
            if DIS_B_SIGNALS & signal_types:
                return "DIS-B", 0.65, f"出现弱势信号，进入派发B: {signal_types}"

        elif phase == "DIS-B":
            if "UTAD" in signal_types:
                return "DIS-C", 0.70, "UTAD出现，进入派发C阶段"

        elif phase == "DIS-C":
            if DIS_D_SIGNALS & signal_types:
                return "DIS-D", 0.75, f"弱势加剧，进入派发D: {signal_types}"

        elif phase == "DIS-D":
            if state.tr_lower > 0 and close < state.tr_lower * 0.97 and state.duration_days >= 5:
                return "MKD", 0.75, "跌破TR下轨，进入下跌趋势"

        elif phase == "TR_UNDETERMINED":
            if "Spring" in signal_types or "SOS" in signal_types:
                return "ACC-A", 0.55, "出现吸筹信号，偏向吸筹方向"
            if "SOW" in signal_types or "UT" in signal_types:
                return "DIS-A", 0.55, "出现派发信号，偏向派发方向"

        return None, 0.0, ""

    def _detect_initial_phase(self, signal_types: set, df: pd.DataFrame) -> Tuple[Optional[str], float, str]:
        """从UNKNOWN状态初始判断"""
        if df.empty or len(df) < 20:
            return None, 0.0, ""
        close = df["close"]
        trend = self._calc_trend(close)
        if trend == "DOWN":
            return "MKD", 0.5, "初始判断：下跌趋势"
        elif trend == "UP":
            return "MKU", 0.5, "初始判断：上涨趋势"
        elif "SC" in signal_types:
            return "ACC-A", 0.55, "初始判断：出现SC，可能吸筹A"
        elif "BC" in signal_types:
            return "DIS-A", 0.55, "初始判断：出现BC，可能派发A"
        return "TR_UNDETERMINED", 0.4, "初始判断：方向未定"

    def _transition(self, state: PhaseState, new_phase: str, date: str,
                    confidence: float, reason: str, df: pd.DataFrame = None):
        """执行状态转移"""
        old_phase = state.phase_code
        # 关闭旧阶段
        if old_phase != "UNKNOWN":
            self.storage.execute(
                "UPDATE wyckoff_phase SET end_date=? WHERE stock_code=? AND timeframe=? AND end_date IS NULL",
                (date, state.stock_code, state.timeframe)
            )
        # 开启新阶段
        state.phase_code = new_phase
        state.confidence = confidence
        state.start_date = date
        state.evidence_chain.append(f"{date}: {old_phase}→{new_phase} ({reason})")
        if df is not None:
            self._update_tr(state, df)
        logger.info(f"[{state.stock_code}] 阶段转移: {old_phase} → {new_phase}（置信度{confidence:.0%}）: {reason}")

    def _update_tr(self, state: PhaseState, df: pd.DataFrame):
        """更新TR区间（支撑/阻力）"""
        acc_dis_phases = set(PHASES.keys()) - {"MKD", "MKU", "UNKNOWN"}
        if state.phase_code not in acc_dis_phases:
            return
        if df.empty or len(df) < 5:
            return
        period = min(len(df), 60)
        recent = df.tail(period)
        candidate_upper = recent["high"].quantile(0.85)
        candidate_lower = recent["low"].quantile(0.15)
        if state.tr_upper == 0:
            state.tr_upper = candidate_upper
            state.tr_lower = candidate_lower
        # 渐进更新，不急剧变化
        state.tr_upper = state.tr_upper * 0.9 + candidate_upper * 0.1
        state.tr_lower = state.tr_lower * 0.9 + candidate_lower * 0.1
        # Creek线（TR上轨附近的阻力）和Ice线（TR下轨）
        if state.creek_line == 0:
            state.creek_line = state.tr_upper * 0.97
        if state.ice_line == 0:
            state.ice_line = state.tr_lower * 1.03

    def _save(self, state: PhaseState):
        self.storage.save_phase(state.stock_code, {
            "phase_code": state.phase_code,
            "start_date": state.start_date or datetime.now().date().isoformat(),
            "end_date": None,
            "confidence": state.confidence,
            "tr_upper": state.tr_upper,
            "tr_lower": state.tr_lower,
            "ice_line": state.ice_line,
            "creek_line": state.creek_line,
            "timeframe": state.timeframe,
        })

    @staticmethod
    def _calc_trend(close: pd.Series) -> str:
        """简单趋势判断"""
        if len(close) < 20:
            return "SIDEWAYS"
        ma_short = close.tail(10).mean()
        ma_long = close.tail(30).mean() if len(close) >= 30 else close.mean()
        if ma_short > ma_long * 1.03:
            return "UP"
        elif ma_short < ma_long * 0.97:
            return "DOWN"
        return "SIDEWAYS"

    @staticmethod
    def _calc_duration(start_date: str, today: str) -> int:
        """计算阶段持续天数"""
        try:
            s = datetime.strptime(start_date, "%Y-%m-%d")
            t = datetime.strptime(today, "%Y-%m-%d")
            return max(0, (t - s).days)
        except Exception:
            return 0

    def get_phase_info(self, phase_code: str) -> dict:
        return PHASES.get(phase_code, PHASES["UNKNOWN"])

    def get_tr_restrictions(self, state: PhaseState) -> dict:
        """获取当前阶段的交易限制"""
        if state.phase_code == "TR_UNDETERMINED":
            return {"buy": False, "sell": False, "allowed": "WAIT_ONLY"}
        acc_phases = [k for k in PHASES if k.startswith("ACC")]
        dis_phases = [k for k in PHASES if k.startswith("DIS")]
        if state.phase_code in acc_phases:
            return {"buy": True, "sell": False, "allowed": "BUY_ONLY"}
        elif state.phase_code in dis_phases:
            return {"buy": False, "sell": True, "allowed": "SELL_ONLY"}
        elif state.phase_code == "MKU":
            return {"buy": True, "sell": False, "allowed": "HOLD_OR_BUY"}
        elif state.phase_code == "MKD":
            return {"buy": False, "sell": True, "allowed": "CASH_OR_SHORT"}
        return {"buy": False, "sell": False, "allowed": "UNKNOWN"}
