"""
ui/components/counter_evidence_bar.py — 反面证据积分仪表盘（V3.1）
"""
import streamlit as st


ALERT_STYLES = {
    "NONE":   {"color": "#2ecc71", "bg": "#1a3a1a", "label": "正常", "emoji": "✅"},
    "YELLOW": {"color": "#f1c40f", "bg": "#3a3a1a", "label": "假设受质疑", "emoji": "⚠️"},
    "ORANGE": {"color": "#e67e22", "bg": "#3a2a1a", "label": "暂停买入", "emoji": "🟠"},
    "RED":    {"color": "#e74c3c", "bg": "#3a1a1a", "label": "紧急反转！", "emoji": "🚨"},
}


def render_counter_evidence_bar(score: float, alert_level: str, events: list = None):
    """渲染反面证据积分仪表盘"""
    style = ALERT_STYLES.get(alert_level, ALERT_STYLES["NONE"])
    score_pct = min(100, max(0, score))
    bar_width = score_pct

    st.markdown(f"""
    <div style="background: {style['bg']}; border: 1px solid {style['color']}44;
                border-radius: 10px; padding: 14px; margin-bottom: 8px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="color: #aaa; font-size: 13px; font-weight: 600;">
                {style['emoji']} 反面证据积分
            </span>
            <span style="color: {style['color']}; font-size: 18px; font-weight: 700;">
                {score:.1f} / 100 &nbsp;·&nbsp; {style['label']}
            </span>
        </div>
        <div style="height: 8px; background: #2a2a2a; border-radius: 4px; overflow: hidden;">
            <div style="height: 100%; width: {bar_width}%; background: {style['color']};
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
