"""
ui/components/phase_bar.py — 阶段进度条组件
"""
import streamlit as st
from engine.phase_fsm import PHASES


PHASE_ORDER = [
    "MKD", "ACC-A", "ACC-B", "ACC-C", "ACC-D", "ACC-E",
    "MKU", "DIS-A", "DIS-B", "DIS-C", "DIS-D", "TR_UNDETERMINED",
]


def render_phase_bar(phase_code: str, confidence: float, duration_days: int = 0):
    """渲染阶段指示条"""
    info = PHASES.get(phase_code, PHASES.get("UNKNOWN", {}))
    color = info.get("color", "#95a5a6")
    name = info.get("name", "未知")
    conf_pct = round(confidence * 100) if confidence <= 1 else round(confidence)

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {color}22, {color}44);
                border-left: 4px solid {color}; border-radius: 8px;
                padding: 12px 16px; margin-bottom: 8px;">
        <div style="color: {color}; font-size: 13px; font-weight: 600; margin-bottom: 4px;">
            📍 当前阶段
        </div>
        <div style="color: #e0e0e0; font-size: 20px; font-weight: 700;">
            {phase_code} — {name}
        </div>
        <div style="color: #aaa; font-size: 13px; margin-top: 4px;">
            置信度 {conf_pct}% · 已持续 {duration_days} 天
        </div>
    </div>
    """, unsafe_allow_html=True)
