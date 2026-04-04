"""
ui/components/signal_panel.py — 信号面板组件
"""
import streamlit as st
import pandas as pd


SIGNAL_EMOJI = {
    "SC": "🔴", "AR": "🟠", "ST": "🟡", "Spring": "🟢",
    "SOS": "💚", "SOW": "🔻", "UT": "🟣", "UTAD": "🔮",
    "JOC": "💫", "LPSY": "🔺", "VDB": "💧", "BC": "🔵", "PSY": "⚪",
}

SIGNAL_DESC = {
    "SC": "卖出高潮", "AR": "自动反弹", "ST": "二次测试", "Spring": "弹簧/震仓",
    "SOS": "力量信号", "SOW": "弱点信号", "UT": "向上试探", "UTAD": "末期试探",
    "JOC": "跳出冰点", "LPSY": "最后供应点", "VDB": "低量测试", "BC": "买入高潮", "PSY": "初步供给",
}


def render_signal_panel(signals: list, title: str = "信号检测"):
    """渲染信号面板"""
    st.markdown(f"#### {title}")
    if not signals:
        st.caption("暂无信号")
        return

    # 排序：似然度从高到低
    sigs = sorted(signals, key=lambda s: s.get("likelihood", 0), reverse=True)

    for sig in sigs:
        sig_type = sig.get("signal_type", "?")
        lik = sig.get("likelihood", 0)
        strength = sig.get("strength", 1)
        date = sig.get("signal_date", "")[:10]
        price = sig.get("trigger_price", 0)
        falsi = sig.get("ai_falsification_result", None)
        emoji = SIGNAL_EMOJI.get(sig_type, "⚡")
        desc = SIGNAL_DESC.get(sig_type, sig_type)

        # 似然度颜色
        if lik >= 0.75:
            lik_color = "#2ecc71"
        elif lik >= 0.50:
            lik_color = "#f39c12"
        else:
            lik_color = "#e74c3c"

        # 证伪结果标记
        falsi_badge = ""
        if falsi == "GENUINE":
            falsi_badge = '<span style="color:#2ecc71; font-size:11px;">✅AI确认</span>'
        elif falsi == "SUSPECT":
            falsi_badge = '<span style="color:#f39c12; font-size:11px;">⚠️AI可疑</span>'
        elif falsi == "FALSE":
            falsi_badge = '<span style="color:#e74c3c; font-size:11px;">❌AI否定</span>'

        strength_stars = "⭐" * strength

        st.markdown(f"""
        <div style="border: 1px solid #333; border-radius: 8px; padding: 10px 14px;
                    margin-bottom: 6px; background: #1a1a1a;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="font-size: 16px;">{emoji}</span>
                    <span style="color: #e0e0e0; font-weight: 700; margin-left: 6px;">{sig_type}</span>
                    <span style="color: #888; font-size: 12px; margin-left: 6px;">{desc}</span>
                    <span style="margin-left: 8px;">{falsi_badge}</span>
                </div>
                <div style="text-align: right; font-size: 12px; color: #aaa;">
                    {date} · ¥{price:.2f} · {strength_stars}
                </div>
            </div>
            <div style="margin-top: 6px; background: #2a2a2a; border-radius: 4px; height: 5px;">
                <div style="width: {lik*100:.0f}%; height: 100%; background: {lik_color}; border-radius: 4px;"></div>
            </div>
            <div style="color: {lik_color}; font-size: 12px; margin-top: 3px;">
                似然度 {lik:.0%}
            </div>
        </div>
        """, unsafe_allow_html=True)
