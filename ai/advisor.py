"""
ai/advisor.py — L4: AI 投资建议生成器
融合量化评分 + 证伪结果，通过门控机制生成最终建议。
参考文档 2.5 节。
"""
from __future__ import annotations
import os
import re
from dataclasses import dataclass
from typing import Dict, Optional
from loguru import logger

from ai.falsification_aggregator import downgrade_advice

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")


def _safe_format(template: str, **kwargs) -> str:
    """Replace {identifier} placeholders only; leave JSON braces untouched."""
    def replace(m):
        key = m.group(1)
        return str(kwargs[key]) if key in kwargs else m.group(0)
    return re.sub(r'\{([A-Za-z_]\w*)\}', replace, template)


def _load_template(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"Prompt模板未找到: {path}")
        return ""


@dataclass
class QuantScores:
    """量化评分汇总"""
    market_alignment: float = 0.0   # 大盘共振 /30
    phase_score: float = 0.0        # 阶段得分 /25
    chain_score: float = 0.0        # 信号链 /20
    mtf_score: float = 0.0          # 多时间框架 /15
    sd_score_10: float = 0.0        # 供需 /10
    total: float = 0.0              # 总分 /100
    nine_tests_passed: int = 0
    nine_tests_detail: str = ""
    counter_score: float = 0.0
    alert_level: str = "NONE"

    def calc_total(self):
        self.total = round(
            self.market_alignment + self.phase_score +
            self.chain_score + self.mtf_score + self.sd_score_10, 1
        )
        return self.total


@dataclass
class UserContext:
    """用户持仓上下文"""
    holding: bool = False
    holding_qty: int = 0
    cost_price: float = 0.0
    current_price: float = 0.0

    @property
    def unrealized_pnl(self) -> str:
        if not self.holding or self.cost_price <= 0:
            return "未持仓"
        pct = (self.current_price - self.cost_price) / self.cost_price * 100
        return f"{pct:+.1f}%"


class AIAdvisor:
    """
    L4 投资建议生成器。
    - 先检查门控（BLOCK返回WAIT，DOWNGRADE降级）
    - 再调用LLM生成详细建议
    - LLM不可用时返回规则引擎生成的基础建议
    """

    def __init__(self, llm_client, config: dict):
        self.llm = llm_client
        self.config = config

    def generate_advice(self, stock_code: str, quant_scores: QuantScores,
                        falsification_adj: Dict, user_context: UserContext,
                        channel_levels=None, pnf_targets: dict = None) -> Dict:
        """
        生成最终投资建议。
        返回包含 advice_type/confidence/summary/reasoning/trade_plan 的字典。
        """
        # ── 门控检查 ──
        gate = falsification_adj.get("advice_gate", "PASS")
        if gate == "BLOCK":
            return {
                "advice_type": "WAIT",
                "confidence": 0,
                "summary": "证伪检验未通过，暂不生成建议",
                "reasoning": "反面证据积分过高或关键信号被AI证伪，建议等待更明确信号",
                "trade_plan": {},
                "key_watch_points": ["关注反面证据积分是否下降", "等待新的确认信号"],
                "invalidation": "N/A",
                "valid_until": "待定",
                "alerts": falsification_adj.get("alerts", []),
                "generated_by": "GATE_BLOCK",
            }

        # ── LLM不可用：规则引擎备用 ──
        if not self.llm.is_available():
            return self._rule_based_advice(stock_code, quant_scores, falsification_adj, user_context, channel_levels, pnf_targets)

        # ── 调用LLM生成建议 ──
        advice = self._call_llm(stock_code, quant_scores, falsification_adj, user_context, channel_levels, pnf_targets)

        # ── 门控降级 ──
        if advice and gate == "DOWNGRADE":
            advice = downgrade_advice(advice)

        advice["generated_by"] = "AI_LLM"
        advice["alerts"] = falsification_adj.get("alerts", [])
        return advice

    def _call_llm(self, stock_code: str, qs: QuantScores, adj: Dict,
                  uc: UserContext, channel_levels, pnf_targets: dict) -> Dict:
        """构建Prompt并调用DeepSeek"""
        template = _load_template("advice_generation.md")
        if not template:
            return self._rule_based_advice(stock_code, qs, adj, uc, channel_levels, pnf_targets)

        support_1 = getattr(channel_levels, "support_1", 0) if channel_levels else 0
        support_2 = getattr(channel_levels, "support_2", 0) if channel_levels else 0
        resistance_1 = getattr(channel_levels, "resistance_1", 0) if channel_levels else 0
        resistance_2 = getattr(channel_levels, "resistance_2", 0) if channel_levels else 0
        pnf_target = (pnf_targets or {}).get("count_target", 0)
        target_1 = resistance_1 or 0
        target_2 = resistance_2 or 0
        stop_loss_ref = support_1 * 0.98 if support_1 else 0

        # 九大检验格式化
        nine_tests_str = qs.nine_tests_detail or f"通过 {qs.nine_tests_passed}/9 项"

        prompt = _safe_format(
            template,
            stock_code=stock_code,
            market_alignment=qs.market_alignment,
            phase_score=qs.phase_score,
            chain_score=qs.chain_score,
            mtf_score=qs.mtf_score,
            sd_score=qs.sd_score_10,
            total_score=qs.total,
            nine_tests_detail=nine_tests_str,
            nine_tests_passed=qs.nine_tests_passed,
            phase_code="",
            phase_name="",
            phase_confidence=round((qs.phase_score / 25) * 100),
            counter_score=round(qs.counter_score),
            alert_level=qs.alert_level,
            to_reversal=max(0, 71 - qs.counter_score),
            falsification_summary=adj.get("phase_falsification_summary", "未执行"),
            support_1=support_1,
            support_2=support_2,
            resistance_1=resistance_1,
            resistance_2=resistance_2,
            stop_loss_ref=round(stop_loss_ref, 2),
            target_1=round(target_1, 2),
            target_2=round(target_2, 2),
            pnf_target=round(pnf_target, 2),
            holding_status="持有" if uc.holding else "空仓",
            cost_price=uc.cost_price,
            unrealized_pnl=uc.unrealized_pnl,
        )

        result = self.llm.chat_json([{"role": "user", "content": prompt}])
        if result and "advice_type" in result:
            return result
        return self._rule_based_advice(stock_code, qs, adj, uc, channel_levels, pnf_targets)

    def _rule_based_advice(self, stock_code: str, qs: QuantScores, adj: Dict,
                           uc: UserContext, channel_levels, pnf_targets: dict) -> Dict:
        """纯规则引擎备用建议（不依赖LLM）"""
        total = qs.total
        counter = qs.counter_score
        alert = qs.alert_level

        # 基础门控
        if counter >= 51:  # 橙色
            advice_type = "WATCH"
            confidence = 40
            summary = f"反面积分{counter:.0f}（橙色预警），暂缓买入"
        elif total >= 80 and qs.nine_tests_passed >= 7 and counter < 31:
            advice_type = "BUY"
            confidence = 75
            summary = f"综合得分{total:.0f}，九大检验{qs.nine_tests_passed}/9，具备买入条件"
        elif total >= 65 and qs.nine_tests_passed >= 5:
            advice_type = "WATCH"
            confidence = 60
            summary = f"综合得分{total:.0f}，条件接近，密切关注"
        elif total >= 50:
            advice_type = "WATCH"
            confidence = 50
            summary = "综合条件中性，继续等待"
        else:
            advice_type = "WAIT"
            confidence = 30
            summary = "综合条件偏弱，不宜操作"

        # 计算参考止损/目标
        support = getattr(channel_levels, "support_1", 0) if channel_levels else 0
        resistance = getattr(channel_levels, "resistance_1", 0) if channel_levels else 0
        current = uc.current_price or support * 1.05
        stop_loss = support * 0.98 if support else 0
        rr = round((resistance - current) / (current - stop_loss), 1) if current > stop_loss > 0 and resistance > current else 0

        return {
            "advice_type": advice_type,
            "confidence": confidence,
            "summary": summary,
            "reasoning": f"量化总分{total:.0f}/100，九大检验{qs.nine_tests_passed}/9，反面积分{counter:.0f}（{alert}）",
            "trade_plan": {
                "entry_price": round(current, 2),
                "entry_mode": "观察",
                "stop_loss": round(stop_loss, 2),
                "target_1": round(resistance, 2),
                "target_2": round(resistance * 1.1, 2),
                "position_pct": 30 if advice_type == "BUY" else 0,
                "rr_ratio": rr,
            },
            "key_watch_points": [
                f"止损参考: {stop_loss:.2f}",
                f"目标参考: {resistance:.2f}",
                "持续关注反面证据积分变化",
            ],
            "invalidation": f"价格跌破 {stop_loss:.2f}",
            "valid_until": "5个交易日",
            "generated_by": "RULE_ENGINE",
        }


def build_quant_scores(phase_state, chain, nine_tests_result: tuple,
                       sd_score: float, mtf_alignment, ce_result: dict) -> QuantScores:
    """从各模块结果汇总量化评分"""
    qs = QuantScores()

    # 阶段得分 /25
    from engine.phase_fsm import PHASES
    phase_code = getattr(phase_state, "phase_code", "UNKNOWN")
    phase_direction = {"ACC-C": 20, "ACC-D": 25, "ACC-B": 15, "ACC-E": 22,
                       "MKU": 20, "ACC-A": 10}.get(phase_code, 5)
    qs.phase_score = round(phase_direction * getattr(phase_state, "confidence", 0.5), 1)

    # 信号链完成度 /20
    chain_pct = getattr(chain, "completion_pct", 0) if chain else 0
    qs.chain_score = round(chain_pct / 100 * 20, 1)

    # 多时间框架 /15
    qs.mtf_score = round(getattr(mtf_alignment, "alignment_score", 0) / 100 * 15, 1) if mtf_alignment else 0

    # 供需 /10
    qs.sd_score_10 = round((sd_score + 100) / 200 * 10, 1)  # -100~+100 → 0~10

    # 大盘共振 /30（暂时用MTF alignment粗代）
    qs.market_alignment = min(30.0, qs.mtf_score * 2)

    # 九大检验
    if nine_tests_result:
        results, passed = nine_tests_result
        qs.nine_tests_passed = passed
        qs.nine_tests_detail = "\n".join(
            f"{'✅' if r.passed else '❌'} {r.name}: {r.detail}"
            for r in results.values()
        )

    # 反面积分
    qs.counter_score = ce_result.get("score", 0)
    qs.alert_level = ce_result.get("alert_level", "NONE")

    qs.calc_total()
    return qs
