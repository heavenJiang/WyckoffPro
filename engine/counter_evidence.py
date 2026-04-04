"""
engine/counter_evidence.py — 反面证据积分追踪器（V3.1核心）
维护每只股票在特定阶段假设下的反面证据积分(0-100)，三级预警，触发紧急反转。
参考文档第三部分。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import pandas as pd
from loguru import logger


ALERT_NONE = "NONE"
ALERT_YELLOW = "YELLOW"    # 31-50
ALERT_ORANGE = "ORANGE"    # 51-70
ALERT_RED = "RED"          # 71-100


@dataclass
class CEEvent:
    """反面/正面证据事件记录"""
    event_type: str
    delta: int
    date: str
    description: str
    source: str = "RULE"  # RULE / AI


@dataclass
class CEState:
    """某只股票的反面证据状态"""
    stock_code: str
    hypothesis: str           # ACCUMULATION / DISTRIBUTION
    score: float = 0.0
    alert_level: str = ALERT_NONE
    events: List[CEEvent] = field(default_factory=list)
    last_updated: str = ""
    reversal_triggered: bool = False
    reversal_target: str = ""
    reversal_reasoning: str = ""


# ─── 吸筹假设下的反面事件积分表 ───
ACC_COUNTER_EVENTS = {
    "SPRING_FAIL":          {"delta": +25, "condition": "ACC-C",  "desc": "Spring失败（3日未收回支撑）"},
    "SPRING_FAIL_VOL":      {"delta": +15, "condition": "ACC-C",  "desc": "Spring失败放量加重"},
    "SOW":                  {"delta": +30, "condition": "ACC-B/C", "desc": "SOW出现（供应控制市场）"},
    "WEAK_RALLY":           {"delta": +20, "condition": "ACC-B/C", "desc": "反弹无需求（连续2次缩量递减）"},
    "UT":                   {"delta": +15, "condition": "ACC-B/C", "desc": "UT出现（吸筹区内出货信号）"},
    "VOL_REVERSE":          {"delta": +20, "condition": "ANY_ACC", "desc": "量价特征逆转（下跌波量>上涨波量）"},
    "SC_BREAK":             {"delta": +35, "condition": "ANY_ACC", "desc": "SC低点被有效跌破（5日未收回）"},
    "NORTH_OUTFLOW":        {"delta": +10, "condition": "ANY_ACC", "desc": "北向资金持续流出（连续10日）"},
}

# ─── 正面证据消减表 ───
ACC_POSITIVE_EVENTS = {
    "ST_SUCCESS":           {"delta": -15, "desc": "成功缩量ST"},
    "SOS":                  {"delta": -25, "desc": "SOS出现"},
    "SPRING_CONFIRMED":     {"delta": -30, "desc": "Spring成功确认"},
    "VDB":                  {"delta": -10, "desc": "VDB出现"},
}


class CounterEvidenceTracker:
    """
    反面证据积分追踪器。
    - 内存状态 + 持久化到 storage
    - 每根新K线检查事件
    - 每交易日自然衰减0.5分
    """

    def __init__(self, config: dict, storage):
        self.config = config.get("emergency_reversal", {})
        self.storage = storage
        self._states: Dict[str, CEState] = {}
        self.yellow_threshold = self.config.get("yellow_alert_threshold", 31)
        self.orange_threshold = self.config.get("orange_alert_threshold", 51)
        self.red_threshold = self.config.get("red_reversal_threshold", 71)
        self.decay_per_day = self.config.get("score_decay_per_day", 0.5)
        self.score_max = self.config.get("score_max", 100)

    def get_state(self, stock_code: str) -> CEState:
        """获取或从DB加载状态"""
        if stock_code not in self._states:
            db_data = self.storage.get_counter_evidence(stock_code)
            if db_data:
                state = CEState(
                    stock_code=stock_code,
                    hypothesis=db_data.get("hypothesis", "ACCUMULATION"),
                    score=db_data.get("current_score", 0.0),
                    alert_level=db_data.get("alert_level", ALERT_NONE),
                    events=[CEEvent(**e) for e in (db_data.get("events") or [])],
                    last_updated=db_data.get("last_updated", ""),
                )
                self._states[stock_code] = state
            else:
                self._states[stock_code] = CEState(
                    stock_code=stock_code,
                    hypothesis="ACCUMULATION",
                    score=0.0,
                )
        return self._states[stock_code]

    def reset(self, stock_code: str, hypothesis: str = "ACCUMULATION"):
        """重置为新假设（阶段转换时调用）"""
        self._states[stock_code] = CEState(
            stock_code=stock_code,
            hypothesis=hypothesis,
            score=0.0,
        )
        self._save(stock_code)
        logger.info(f"[{stock_code}] 反面积分重置，新假设: {hypothesis}")

    def update(self, stock_code: str, bar: pd.Series, context: dict, signals: list) -> dict:
        """
        处理新K线，更新反面积分。
        返回结果字典，包括是否触发反转。
        """
        state = self.get_state(stock_code)
        today = str(bar.get("trade_date", datetime.now().date()))

        # 1. 每日衰减
        state.score = max(0.0, state.score - self.decay_per_day)

        # 2. 检查各类事件
        if state.hypothesis == "ACCUMULATION":
            self._check_acc_events(state, bar, context, signals, today)
        elif state.hypothesis == "DISTRIBUTION":
            self._check_dis_events(state, bar, context, signals, today)

        # 3. 计算告警级别
        state.score = min(self.score_max, max(0.0, state.score))
        state.alert_level = self._calc_alert_level(state.score)
        state.last_updated = today

        # 4. 检查紧急反转
        result = self._check_emergency_reversal(state)

        # 5. 持久化
        self._save(stock_code)
        return result

    def adjust_score(self, stock_code: str, delta: float, source: str = "AI", desc: str = "AI证伪调整"):
        """外部（AI证伪结果）调整积分"""
        state = self.get_state(stock_code)
        state.score = min(self.score_max, max(0.0, state.score + delta))
        state.alert_level = self._calc_alert_level(state.score)
        event = CEEvent(
            event_type="AI_ADJUSTMENT",
            delta=int(delta),
            date=datetime.now().date().isoformat(),
            description=desc,
            source=source
        )
        state.events.append(event)
        self._save(stock_code)
        logger.debug(f"[{stock_code}] AI调整积分 {delta:+.0f} → {state.score:.1f}（{state.alert_level}）")

    def get_score(self, stock_code: str) -> float:
        return self.get_state(stock_code).score

    def get_alert_level(self, stock_code: str) -> str:
        return self.get_state(stock_code).alert_level

    # ─── 内部检查逻辑 ───

    def _check_acc_events(self, state: CEState, bar: pd.Series, context: dict, signals: list, today: str):
        """检查吸筹假设下的反面事件"""
        signal_types = {s.get("signal_type", "") for s in signals}
        sc_low = context.get("sc_low", 0)
        current_low = bar.get("low", 0)
        atr = context.get("atr_20", bar.get("atr_20", 1))

        # Spring失败判断（需要context中的spring_date和当前日期计算天数）
        if context.get("spring_failed"):
            self._add_event(state, "SPRING_FAIL", today, +25, "RULE")
            if context.get("spring_vol_expanding"):
                self._add_event(state, "SPRING_FAIL_VOL", today, +15, "RULE")

        # SOW出现
        if "SOW" in signal_types:
            self._add_event(state, "SOW", today, +30, "RULE")

        # UT出现
        if "UT" in signal_types:
            self._add_event(state, "UT", today, +15, "RULE")

        # 反弹无需求
        if context.get("weak_rally_count", 0) >= 2:
            self._add_event(state, "WEAK_RALLY", today, +20, "RULE")

        # 量价特征逆转
        if context.get("vol_reversal"):
            self._add_event(state, "VOL_REVERSE", today, +20, "RULE")

        # SC低点被有效跌破
        if sc_low > 0 and current_low < sc_low and context.get("sc_break_days", 0) >= 5:
            self._add_event(state, "SC_BREAK", today, +35, "RULE")

        # 北向持续流出
        if context.get("north_outflow_days", 0) >= 10:
            self._add_event(state, "NORTH_OUTFLOW", today, +10, "RULE")

        # 正面消减
        if context.get("st_success"):
            self._add_event(state, "ST_SUCCESS", today, -15, "RULE")
        if "SOS" in signal_types:
            self._add_event(state, "SOS", today, -25, "RULE")
        if context.get("spring_confirmed"):
            self._add_event(state, "SPRING_CONFIRMED", today, -30, "RULE")
        if "VDB" in signal_types:
            self._add_event(state, "VDB", today, -10, "RULE")

    def _check_dis_events(self, state: CEState, bar: pd.Series, context: dict, signals: list, today: str):
        """检查派发假设下的反面事件（对称逻辑）"""
        signal_types = {s.get("signal_type", "") for s in signals}
        # 派发假设的反面证据：出现吸筹信号（Spring/SOS）
        if "Spring" in signal_types:
            self._add_event(state, "SPRING_IN_DIS", today, +25, "RULE")
        if "SOS" in signal_types:
            self._add_event(state, "SOS_IN_DIS", today, +20, "RULE")
        # 价格持续走强
        if context.get("bc_high_break"):
            self._add_event(state, "BC_BREAK_IN_DIS", today, +30, "RULE")

    def _add_event(self, state: CEState, event_type: str, date: str, delta: int, source: str):
        """添加事件并更新积分"""
        # 同一天同类事件只计一次
        for e in state.events[-20:]:
            if e.event_type == event_type and e.date == date:
                return
        state.score += delta
        event = CEEvent(event_type=event_type, delta=delta, date=date,
                        description=self._get_desc(event_type), source=source)
        state.events.append(event)
        logger.debug(f"[{state.stock_code}] 反面事件: {event_type} {delta:+d} → {state.score:.1f}")

    def _check_emergency_reversal(self, state: CEState) -> dict:
        """检查是否触发紧急反转"""
        result = {
            "score": state.score,
            "alert_level": state.alert_level,
            "reversal_triggered": False,
            "reversal_target": None,
            "reversal_reasoning": None,
        }

        if state.score < self.red_threshold:
            return result

        # 确定反转目标
        event_types = {e.event_type for e in state.events[-30:]}
        has_sc_break = "SC_BREAK" in event_types
        has_sow = "SOW" in event_types
        has_ut = "UT" in event_types
        has_vol_reverse = "VOL_REVERSE" in event_types

        if has_sc_break:
            target = "MKD"
            reasoning = "SC低点被有效跌破，震荡区为下跌中继而非吸筹底部"
        elif has_sow and has_vol_reverse:
            target = "DIS-D"
            reasoning = "SOW+供应主导，原吸筹假设被推翻，真实性质为派发"
        elif has_ut and not has_sow:
            target = "DIS-B"
            reasoning = "出现UT+反弹无需求，可能是派发主体阶段"
        else:
            target = "TR_UNDETERMINED"
            reasoning = "反面证据累积但方向不够明确，进入中性待判定"

        result.update({
            "reversal_triggered": True,
            "reversal_target": target,
            "reversal_reasoning": reasoning,
        })
        state.reversal_triggered = True
        state.reversal_target = target
        state.reversal_reasoning = reasoning

        logger.warning(f"🚨 [{state.stock_code}] 紧急反转触发！积分={state.score:.1f} → {target}: {reasoning}")
        return result

    def _calc_alert_level(self, score: float) -> str:
        if score >= self.red_threshold:
            return ALERT_RED
        elif score >= self.orange_threshold:
            return ALERT_ORANGE
        elif score >= self.yellow_threshold:
            return ALERT_YELLOW
        return ALERT_NONE

    def _save(self, stock_code: str):
        state = self._states[stock_code]
        self.storage.save_counter_evidence(stock_code, {
            "hypothesis": state.hypothesis,
            "current_score": state.score,
            "alert_level": state.alert_level,
            "events": [{"event_type": e.event_type, "delta": e.delta,
                        "date": e.date, "description": e.description, "source": e.source}
                       for e in state.events[-50:]],  # 只保留最近50条
        })

    @staticmethod
    def _get_desc(event_type: str) -> str:
        all_events = {**ACC_COUNTER_EVENTS, **ACC_POSITIVE_EVENTS,
                      "SPRING_IN_DIS": {"desc": "派发假设中出现Spring信号"},
                      "SOS_IN_DIS": {"desc": "派发假设中出现SOS信号"},
                      "BC_BREAK_IN_DIS": {"desc": "价格突破BC高点"},
                      "ST_SUCCESS": {"desc": "成功缩量ST"},
                      "AI_ADJUSTMENT": {"desc": "AI证伪调整"}}
        return all_events.get(event_type, {}).get("desc", event_type)
