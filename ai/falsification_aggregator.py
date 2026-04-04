"""
ai/falsification_aggregator.py — 证伪结果聚合器（V3.1）
聚合三层证伪结果，计算积分调整、信号似然度修正、建议门控。
参考文档 2.4.4 节。
"""
from __future__ import annotations
from typing import Dict, List, Optional
from loguru import logger


class FalsificationAggregator:
    """
    聚合 Prompt A/B/C 的证伪结果，产生系统调整指令。

    输出格式：
    {
        'phase_confidence_delta': int,      # 阶段置信度调整量 (-100~+100)
        'counter_evidence_delta': int,       # 反面积分调整量
        'signal_adjustments': {sig_type: {action, new_likelihood}},
        'advice_gate': str,                  # PASS / BLOCK / DOWNGRADE
        'alerts': [{'level', 'source', 'message'}],
        'phase_falsification_summary': str,
    }
    """

    def process_results(self, stock_code: str,
                        phase_falsification: Optional[Dict],
                        signal_falsifications: Dict[str, Dict],
                        narrative_check: Optional[Dict]) -> Dict:
        """
        聚合三层证伪结果。
        - phase_falsification: Prompt A 结果
        - signal_falsifications: {sig_type: Prompt B结果}
        - narrative_check: Prompt C 结果
        """
        adj = {
            "phase_confidence_delta": 0,
            "counter_evidence_delta": 0,
            "signal_adjustments": {},
            "advice_gate": "PASS",
            "alerts": [],
            "phase_falsification_summary": "未执行",
        }

        # ── Prompt A: 阶段证伪 ──
        adj = self._process_phase(stock_code, phase_falsification, adj)

        # ── Prompt B: 信号证伪 ──
        adj = self._process_signals(signal_falsifications, adj)

        # ── Prompt C: 叙事一致性 ──
        adj = self._process_narrative(narrative_check, adj)

        # 日志
        logger.info(
            f"[{stock_code}] 证伪聚合: gate={adj['advice_gate']}, "
            f"conf_delta={adj['phase_confidence_delta']:+d}, "
            f"ce_delta={adj['counter_evidence_delta']:+d}, "
            f"alerts={len(adj['alerts'])}"
        )
        return adj

    def _process_phase(self, stock_code: str, pf: Optional[Dict], adj: Dict) -> Dict:
        if not pf:
            return adj

        result = pf.get("falsification_result", "")
        adj["phase_falsification_summary"] = f"{result}（AI置信度{pf.get('confidence_in_falsification', 0)}%）"

        if result == "FAILED":
            # 证伪失败 = 假设成立
            adj["phase_confidence_delta"] = +5
            adj["counter_evidence_delta"] = -10
            adj["phase_falsification_summary"] += "，假设成立"

        elif result == "SUCCEEDED":
            adj["phase_confidence_delta"] = -15
            violated = pf.get("violated_conditions", [])
            for v in violated:
                sev = v.get("severity", "MINOR")
                delta = {"CRITICAL": 25, "MAJOR": 15, "MINOR": 5}.get(sev, 5)
                adj["counter_evidence_delta"] += delta
                if sev == "CRITICAL":
                    adj["alerts"].append({
                        "level": "CRITICAL",
                        "source": "AI_PHASE_FALSIFICATION",
                        "message": f"AI阶段证伪发现严重矛盾：{v.get('condition', '')}"
                    })

            # 替代假设
            alt = pf.get("alternative_hypothesis", {})
            if alt.get("confidence", 0) >= 70:
                adj["alerts"].append({
                    "level": "WARNING",
                    "source": "AI_ALTERNATIVE",
                    "message": f"AI认为真实阶段可能是 {alt.get('phase')}（{alt.get('confidence')}%）"
                })

        elif result == "PARTIAL":
            adj["phase_confidence_delta"] = -5
            adj["counter_evidence_delta"] += 8

        return adj

    def _process_signals(self, signal_fs: Dict[str, Dict], adj: Dict) -> Dict:
        CRITICAL_SIGNAL_TYPES = {"Spring", "JOC", "BreakIce", "LPSY"}

        for sig_type, sf in signal_fs.items():
            if not sf:
                continue
            result = sf.get("falsification_result", "")
            original_likelihood = sf.get("original_likelihood", 0.5)

            if result == "FALSE":
                adj["signal_adjustments"][sig_type] = {
                    "action": "INVALIDATE",
                    "new_likelihood": max(0.1, original_likelihood * 0.3),
                }
                if sig_type in CRITICAL_SIGNAL_TYPES:
                    adj["advice_gate"] = "BLOCK"
                    adj["alerts"].append({
                        "level": "CRITICAL",
                        "source": "AI_SIGNAL_FALSIFICATION",
                        "message": f"关键信号 {sig_type} 被AI证伪为假信号，建议已阻止"
                    })

            elif result == "SUSPECT":
                adj["signal_adjustments"][sig_type] = {
                    "action": "DOWNGRADE",
                    "new_likelihood": original_likelihood * 0.7,
                }
                if sig_type in CRITICAL_SIGNAL_TYPES and adj["advice_gate"] == "PASS":
                    adj["advice_gate"] = "DOWNGRADE"
                    adj["alerts"].append({
                        "level": "WARNING",
                        "source": "AI_SIGNAL_SUSPECT",
                        "message": f"关键信号 {sig_type} 被AI标记为可疑，建议降级"
                    })

            elif result == "GENUINE":
                adj["signal_adjustments"][sig_type] = {
                    "action": "CONFIRM",
                    "new_likelihood": min(0.95, original_likelihood * 1.1),
                }

        return adj

    def _process_narrative(self, nc: Optional[Dict], adj: Dict) -> Dict:
        if not nc:
            return adj

        result = nc.get("consistency_result", "")
        contradictions = nc.get("contradictions_found", [])

        for c in contradictions:
            sev = c.get("severity", "MINOR")
            if sev == "CRITICAL":
                adj["advice_gate"] = "BLOCK"
                adj["alerts"].append({
                    "level": "CRITICAL",
                    "source": "AI_NARRATIVE",
                    "message": f"叙事一致性：严重矛盾 — {c.get('description', '')}"
                })
            elif sev == "MAJOR" and adj["advice_gate"] == "PASS":
                adj["advice_gate"] = "DOWNGRADE"
                adj["alerts"].append({
                    "level": "WARNING",
                    "source": "AI_NARRATIVE",
                    "message": f"叙事一致性：重大矛盾 — {c.get('description', '')}"
                })

        score = nc.get("narrative_coherence_score", 100)
        if score < 40:
            adj["counter_evidence_delta"] += 10

        return adj


def downgrade_advice(advice: dict) -> dict:
    """将建议降级一档"""
    ladder = ["STRONG_BUY", "BUY", "WATCH", "HOLD", "REDUCE", "SELL", "STRONG_SELL", "WAIT"]
    current = advice.get("advice_type", "WAIT")
    if current in ladder:
        idx = ladder.index(current)
        if idx + 1 < len(ladder):
            advice["advice_type"] = ladder[idx + 1]
            advice["confidence"] = max(20, advice.get("confidence", 50) - 15)
    return advice
