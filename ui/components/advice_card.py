"""
ui/components/advice_card.py — 投资建议卡片组件
"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from ui.components.translations import CN

# 组件专用样式（颜色/图标，标签由 CN.advice() 提供）
ADVICE_STYLES = {
    "STRONG_BUY":  {"color": "#00e676", "bg": "#0a2a0a", "icon": "🚀"},
    "BUY":         {"color": "#66bb6a", "bg": "#1a2a1a", "icon": "📈"},
    "WATCH":       {"color": "#29b6f6", "bg": "#0a1a2a", "icon": "👁"},
    "HOLD":        {"color": "#78909c", "bg": "#1a2030", "icon": "🤚"},
    "REDUCE":      {"color": "#ffa726", "bg": "#2a1a0a", "icon": "📉"},
    "SELL":        {"color": "#ef5350", "bg": "#2a0a0a", "icon": "🔻"},
    "STRONG_SELL": {"color": "#ff1744", "bg": "#3a0a0a", "icon": "💥"},
    "WAIT":        {"color": "#78909c", "bg": "#1a1a1a", "icon": "⏳"},
}


def render_advice_card(advice: dict):
    """渲染投资建议卡片"""
    advice_type = advice.get("advice_type", "WAIT")
    style = ADVICE_STYLES.get(advice_type, ADVICE_STYLES["WAIT"])
    label = CN.advice(advice_type)
    conf = advice.get("confidence", 0)
    summary = advice.get("summary", "暂无建议")
    reasoning = advice.get("reasoning", "")
    generated_by = advice.get("generated_by", "RULE_ENGINE")
    alerts = advice.get("alerts", [])

    # 主卡片
    st.markdown(f"""
    <div style="background: {style['bg']}; border: 1px solid {style['color']}55;
                border-left: 5px solid {style['color']}; border-radius: 12px;
                padding: 20px; margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
                <div style="color: {style['color']}; font-size: 28px; font-weight: 800;">
                    {style['icon']} {label}
                </div>
                <div style="color: #e0e0e0; font-size: 16px; margin-top: 6px;">
                    {summary}
                </div>
            </div>
            <div style="text-align: right;">
                <div style="color: #aaa; font-size: 12px;">置信度</div>
                <div style="color: {style['color']}; font-size: 32px; font-weight: 700;">{conf}%</div>
                <div style="color: #666; font-size: 11px; margin-top: 4px;">
                    {'🤖 AI生成' if generated_by == 'AI_LLM' else '⚙️ 规则引擎'}
                </div>
            </div>
        </div>
        {'<div style="color: #aaa; font-size: 13px; margin-top: 12px; border-top: 1px solid #333; padding-top: 12px;">' + reasoning + '</div>' if reasoning else ''}
    </div>
    """, unsafe_allow_html=True)

    # 交易计划
    tp = advice.get("trade_plan", {})
    if tp and tp.get("entry_price"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("入场价", f"¥{tp.get('entry_price', 0):.2f}", delta=tp.get("entry_mode", ""))
        with col2:
            sl = tp.get("stop_loss", 0)
            if sl and tp.get("entry_price"):
                diff = (sl - tp["entry_price"]) / tp["entry_price"] * 100
                st.metric("止损", f"¥{sl:.2f}", delta=f"{diff:.1f}%", delta_color="inverse")
        with col3:
            t1 = tp.get("target_1", 0)
            if t1 and tp.get("entry_price"):
                diff1 = (t1 - tp["entry_price"]) / tp["entry_price"] * 100
                st.metric("目标1", f"¥{t1:.2f}", delta=f"+{diff1:.1f}%")
        with col4:
            rr = tp.get("rr_ratio", 0)
            pos = tp.get("position_pct", 0)
            st.metric("盈亏比", f"1:{rr}", delta=f"仓位{pos}%")

    # 关键关注点
    watch_points = advice.get("key_watch_points", [])
    if watch_points:
        st.caption("📋 关键关注点: " + " · ".join(watch_points[:3]))

    # 失效条件
    invalidation = advice.get("invalidation", "")
    if invalidation:
        st.caption(f"❌ 失效条件: {invalidation}")

    # 告警
    for alert in alerts:
        level = alert.get("level", "INFO")
        msg = alert.get("message", "")
        if level == "CRITICAL":
            st.error(f"🚨 {msg}")
        elif level == "WARNING":
            st.warning(f"⚠️ {msg}")
        else:
            st.info(f"ℹ️ {msg}")
