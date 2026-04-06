"""
ui/components/phase_bar.py — 阶段进度条组件
"""
import streamlit as st
from engine.phase_fsm import PHASES
from ui.components.translations import CN


PHASE_ORDER = [
    "MKD", "ACC-A", "ACC-B", "ACC-C", "ACC-D", "ACC-E",
    "MKU", "DIS-A", "DIS-B", "DIS-C", "DIS-D", "TR_UNDETERMINED",
]


def render_phase_bar(phase_code: str, confidence: float, duration_days: int = 0):
    """渲染阶段指示条"""
    info     = PHASES.get(phase_code, PHASES.get("UNKNOWN", {}))
    color    = info.get("color", "#95a5a6")
    cn_name  = CN.phase(phase_code)
    conf_pct = round(confidence * 100) if confidence <= 1 else round(confidence)
    dur_str  = f" · 已持续 {duration_days} 天" if duration_days else ""

    st.markdown(f"""
<div style="background:linear-gradient(135deg,{color}22,{color}44);
            border-left:4px solid {color};border-radius:8px;
            padding:10px 14px;margin-bottom:8px;">
  <div style="color:{color};font-size:11px;font-weight:600;margin-bottom:2px;">
    📍 当前威科夫阶段
  </div>
  <div style="color:#e0e0e0;font-size:15px;font-weight:700;">
    {cn_name}
  </div>
  <div style="color:#9ca3af;font-size:11px;margin-top:3px;">
    <span style="color:{color};">{phase_code}</span>
    &nbsp;·&nbsp;置信度 {conf_pct}%{dur_str}
  </div>
</div>
""", unsafe_allow_html=True)
