"""
ui/components/counter_evidence_bar.py — 反面证据积分仪表盘（V3.1）
"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from ui.components.translations import CN

# 仪表盘专用背景色 / 图标（颜色标签由 CN.alert() 提供）
_ALERT_EXTRA = {
    "NONE":   {"bg": "#1a3a1a", "emoji": "✅"},
    "GREEN":  {"bg": "#1a3a1a", "emoji": "✅"},
    "YELLOW": {"bg": "#3a3a1a", "emoji": "⚠️"},
    "ORANGE": {"bg": "#3a2a1a", "emoji": "🟠"},
    "RED":    {"bg": "#3a1a1a", "emoji": "🚨"},
}


def render_counter_evidence_bar(score: float, alert_level: str, events: list = None):
    """渲染反面证据积分仪表盘"""
    label, color = CN.alert(alert_level)
    extra = _ALERT_EXTRA.get(alert_level, _ALERT_EXTRA["NONE"])
    bg    = extra["bg"]
    emoji = extra["emoji"]
    score_pct = min(100, max(0, score))
    bar_width = score_pct

    st.markdown(f"""
    <div style="background: {bg}; border: 1px solid {color}44;
                border-radius: 10px; padding: 14px; margin-bottom: 8px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="color: #aaa; font-size: 13px; font-weight: 600;">
                {emoji} 反面证据积分
            </span>
            <span style="color: {color}; font-size: 18px; font-weight: 700;">
                {score:.1f} / 100 &nbsp;·&nbsp; {label}
            </span>
        </div>
        <div style="height: 8px; background: #2a2a2a; border-radius: 4px; overflow: hidden;">
            <div style="height: 100%; width: {bar_width}%; background: {color};
                         border-radius: 4px; transition: width 0.5s ease;"></div>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 4px;
                    font-size: 11px; color: #666;">
            <span>0</span>
            <span style="color: #f1c40f;">31</span>
            <span style="color: #e67e22;">51</span>
            <span style="color: #e74c3c;">71</span>
            <span>100</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 最近事件列表
    if events and len(events) > 0:
        with st.expander(f"反面证据事件 ({len(events)}条)", expanded=False):
            for e in reversed(events[-10:]):
                delta = e.get("delta", 0)
                color = "#e74c3c" if delta > 0 else "#2ecc71"
                sign = "+" if delta > 0 else ""
                st.markdown(f"""
                <div style="color: #bbb; font-size: 13px; padding: 3px 0; border-bottom: 1px solid #333;">
                    <span style="color: {color}; font-weight: 700;">{sign}{delta}</span>
                    &nbsp;·&nbsp; {e.get('date','')[:10]}
                    &nbsp;·&nbsp; {e.get('description','')}
                </div>
                """, unsafe_allow_html=True)
