"""
ai/falsification_engine.py — 证伪引擎（V3.1核心）
实现三层证伪：Prompt A（阶段）、Prompt B（信号）、Prompt C（叙事一致性）。
"""
from __future__ import annotations
import os
from typing import Optional, Dict, List
import pandas as pd
from loguru import logger


SIGNAL_CHECKLISTS = {
    "Spring": "spring.md",
    "SC":     "sc.md",
    "JOC":    "joc.md",
    "SOW":    "sow.md",
}

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")


def _load_template(filename: str) -> str:
    """加载Prompt模板文件"""
    path = os.path.join(PROMPTS_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"Prompt模板未找到: {path}")
        return ""


def _load_checklist(signal_type: str) -> str:
    """加载信号专用检查清单"""
    filename = SIGNAL_CHECKLISTS.get(signal_type)
    if not filename:
        return "（无专用检查清单，请根据信号类型常识判断）"
    path = os.path.join(PROMPTS_DIR, "signal_checklists", filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "（检查清单文件未找到）"


def _df_to_table(df: pd.DataFrame, cols: list = None, max_rows: int = 20) -> str:
    """将DataFrame转为Markdown表格"""
    if df.empty:
        return "（无数据）"
    if cols:
        df = df[cols]
    tail = df.tail(max_rows)
    return tail.to_markdown(index=False) if hasattr(tail, "to_markdown") else tail.to_string(index=False)


def _render_prompt(template_str: str, **kwargs) -> str:
    """安全的Prompt内容替换，避免str.format()导致JSON的{}符号抛出KeyError"""
    res = template_str
    for k, v in kwargs.items():
        res = res.replace(f"{{{k}}}", str(v))
    return res


class FalsificationEngine:
    """
    证伪引擎：三层证伪（阶段/信号/叙事一致性）。
    每层均调用LLM，以"唱反调"方式检验FSM判定。
    """

    def __init__(self, llm_client, config: dict):
        self.llm = llm_client
        self.config = config.get("ai", {}).get("falsification", {})

    # ─── Prompt A: 阶段证伪 ───

    def falsify_phase(self, stock_code: str, phase_state,
                      df: pd.DataFrame, context: dict) -> Optional[Dict]:
        """
        Prompt A: 尝试推翻当前阶段假设。
        返回 dict 或 None（AI不可用时）。
        """
        if not self.config.get("prompt_a_enabled", True):
            return None
        if not self.llm.is_available():
            return None

        template = _load_template("phase_falsification.md")
        if not template:
            return None

        kline_table = _df_to_table(df, cols=["trade_date", "open", "high", "low", "close", "volume"])
        phase_info = getattr(phase_state, "phase_code", "UNKNOWN")
        from engine.phase_fsm import PHASES
        phase_name = PHASES.get(phase_info, {}).get("name", "未知")

        prompt = _render_prompt(template,
            stock_code=stock_code,
            phase_code=phase_info,
            phase_name=phase_name,
            phase_start_date=getattr(phase_state, "start_date", "未知"),
            phase_confidence=round(getattr(phase_state, "confidence", 0.5) * 100),
            N=min(len(df), 30),
            kline_table=kline_table,
            fsm_evidence_chain="\n".join(getattr(phase_state, "evidence_chain", [])[-5:]),
        )

        result = self.llm.chat_json([{"role": "user", "content": prompt}])
        if result:
            logger.info(f"[{stock_code}] Prompt A 证伪结果: {result.get('falsification_result')}")
        return result

    # ─── Prompt B: 信号证伪 ───

    def falsify_signal(self, stock_code: str, signal, df: pd.DataFrame,
                       phase_state, context: dict) -> Optional[Dict]:
        """
        Prompt B: 检验某个信号是否是假信号。
        signal: Signal对象或dict。
        """
        if not self.config.get("prompt_b_enabled", True):
            return None
        if not self.llm.is_available():
            return None

        sig_type = signal.signal_type if hasattr(signal, "signal_type") else signal.get("signal_type", "")
        sig_date = signal.signal_date if hasattr(signal, "signal_date") else signal.get("signal_date", "")
        sig_likelihood = signal.likelihood if hasattr(signal, "likelihood") else signal.get("likelihood", 0.5)
        sig_price = signal.trigger_price if hasattr(signal, "trigger_price") else signal.get("trigger_price", 0)
        sig_vol = signal.trigger_volume if hasattr(signal, "trigger_volume") else signal.get("trigger_volume", 0)

        template = _load_template("signal_falsification.md")
        checklist = _load_checklist(sig_type)
        if not template:
            return None

        avg_vol = df["volume"].tail(20).mean() if not df.empty else 1
        vol_ratio = round(sig_vol / (avg_vol + 1e-9), 1)

        # 获取信号日前后K线
        sig_idx = df[df["trade_date"] == sig_date].index
        if len(sig_idx) > 0:
            idx = sig_idx[0]
            context_df = df.iloc[max(0, idx - 10): min(len(df), idx + 4)]
        else:
            context_df = df.tail(14)

        kline_table = _df_to_table(context_df, cols=["trade_date", "open", "high", "low", "close", "volume"])

        recent_signals = context.get("recent_signals_str", "（未知）")
        prompt = _render_prompt(template,
            signal_type=sig_type,
            signal_date=sig_date,
            likelihood=f"{sig_likelihood:.2f}",
            trigger_price=sig_price,
            trigger_volume=sig_vol,
            vol_ratio=vol_ratio,
            current_phase=getattr(phase_state, "phase_code", "UNKNOWN"),
            tr_upper=getattr(phase_state, "tr_upper", 0),
            tr_lower=getattr(phase_state, "tr_lower", 0),
            recent_signals=recent_signals,
            sd_score=context.get("sd_score", "N/A"),
            kline_context_table=kline_table,
            signal_specific_checklist=checklist,
        )

        result = self.llm.chat_json([{"role": "user", "content": prompt}])
        if result:
            logger.info(f"[{stock_code}] Prompt B 信号({sig_type})证伪: {result.get('falsification_result')}")
        return result

    # ─── Prompt C: 叙事一致性检验 ───

    def check_narrative(self, stock_code: str, phase_state, chain,
                        sd_score: float, sd_breakdown: dict,
                        ce_result: dict, mtf_alignment,
                        current_advice: str = "WAIT") -> Optional[Dict]:
        """Prompt C: 检验整体分析叙事的一致性"""
        if not self.config.get("prompt_c_enabled", True):
            return None
        if not self.llm.is_available():
            return None

        template = _load_template("narrative_consistency.md")
        if not template:
            return None

        chain_type = getattr(chain, "chain_type", "N/A") if chain else "N/A"
        chain_pct = getattr(chain, "completion_pct", 0) if chain else 0
        events = getattr(chain, "events", []) if chain else []
        chain_timeline = " → ".join(
            f"{e.signal_type}({e.date})" for e in events
        ) if events else "（无信号链事件）"

        prompt = _render_prompt(template,
            weekly_phase=getattr(mtf_alignment, "weekly_phase", "N/A"),
            weekly_conf=round(getattr(mtf_alignment, "weekly_conf", 0) * 100),
            daily_phase=getattr(phase_state, "phase_code", "N/A"),
            daily_conf=round(getattr(phase_state, "confidence", 0) * 100),
            intra_phase=getattr(mtf_alignment, "intra_phase", "N/A"),
            intra_conf=round(getattr(mtf_alignment, "intra_conf", 0) * 100),
            chain_type=chain_type,
            chain_pct=chain_pct,
            signal_chain_timeline=chain_timeline,
            supports=f"{getattr(phase_state, 'tr_lower', 0):.2f}",
            resistances=f"{getattr(phase_state, 'tr_upper', 0):.2f}",
            ice_line=f"{getattr(phase_state, 'ice_line', 0):.2f}",
            creek_line=f"{getattr(phase_state, 'creek_line', 0):.2f}",
            sd_score=sd_score,
            sd_breakdown=str(sd_breakdown),
            current_advice=current_advice,
            counter_score=round(ce_result.get("score", 0)),
            alert_level=ce_result.get("alert_level", "NONE"),
        )

        result = self.llm.chat_json([{"role": "user", "content": prompt}])
        if result:
            logger.info(f"[{stock_code}] Prompt C 一致性: {result.get('consistency_result')}, 得分={result.get('narrative_coherence_score')}")
        return result
