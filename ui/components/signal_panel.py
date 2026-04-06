"""
ui/components/signal_panel.py — 信号面板组件
"""
import streamlit as st
import html as _html
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from ui.components.glossary import GLOSSARY
from ui.components.translations import CN

SIGNAL_EMOJI = {
    "SC": "🔴", "AR": "🟠", "ST": "🟡", "Spring": "🟢",
    "SOS": "💚", "SOW": "🔻", "UT": "🟣", "UTAD": "🔮",
    "JOC": "💫", "LPSY": "🔺", "VDB": "💧", "BC": "🔵", "PSY": "⚪",
}


def render_signal_panel(signals: list, title: str = "信号检测"):
    """渲染信号面板"""
    st.markdown(f"#### {title}")
    if not signals:
        st.caption("暂无信号")
        return

    sigs = sorted(signals, key=lambda s: s.get("likelihood", 0), reverse=True)

    for sig in sigs:
        sig_type = sig.get("signal_type", "?")
        lik      = sig.get("likelihood", 0)
        strength = sig.get("strength", 1)
        sig_date = sig.get("signal_date", "")[:10]
        price    = sig.get("trigger_price", 0)
        falsi    = sig.get("ai_falsification_result", None)
        emoji    = SIGNAL_EMOJI.get(sig_type, "⚡")
        desc_cn  = CN.signal(sig_type)

        lik_color = "#2ecc71" if lik >= 0.75 else ("#f39c12" if lik >= 0.50 else "#e74c3c")

        falsi_badge = ""
        if falsi:
            falsi_cn  = CN.verdict(falsi)
            falsi_clr = "#2ecc71" if "确认" in falsi_cn else ("#f39c12" if "可疑" in falsi_cn else "#e74c3c")
            falsi_badge = f'&nbsp;<span style="color:{falsi_clr};font-size:10px;">{_html.escape(falsi_cn)}</span>'

        strength_stars = "⭐" * max(1, min(strength or 1, 5))

        # 转义 GLOSSARY 中含 >/< 的内容（避免破坏 title 属性 HTML 结构）
        _raw_def = GLOSSARY.get(sig_type, "").replace("\n", " | ")
        definition = _html.escape(_raw_def, quote=True)
        def_tip = f' title="{definition}"' if definition else ""

        # 用 <span style="display:inline-block"> 代替裸 <div>，避免 Streamlit 剥离无属性 div
        st.markdown(
            f'<div style="border:1px solid #2d2d2d;border-radius:8px;padding:8px 12px;'
            f'margin-bottom:5px;background:#161616;">'
            f'<span style="display:flex;justify-content:space-between;align-items:center;">'
            f'<span style="flex:1;overflow:hidden;">'
            f'<span style="font-size:14px;">{emoji}</span>'
            f'<span style="color:#e0e0e0;font-weight:700;font-size:13px;margin-left:5px;">{_html.escape(desc_cn)}</span>'
            f'<span{def_tip} style="color:#6b7280;font-size:11px;margin-left:3px;border-bottom:1px dashed #444;cursor:help;">({_html.escape(sig_type)})</span>'
            f'{falsi_badge}'
            f'</span>'
            f'<span style="white-space:nowrap;font-size:11px;color:#9ca3af;margin-left:8px;">'
            f'{sig_date}&nbsp;·&nbsp;¥{price:.2f}&nbsp;·&nbsp;{strength_stars}'
            f'</span>'
            f'</span>'
            f'<div style="margin-top:5px;background:#2a2a2a;border-radius:3px;height:3px;">'
            f'<div style="width:{lik*100:.0f}%;height:100%;background:{lik_color};border-radius:3px;"></div>'
            f'</div>'
            f'<span style="color:{lik_color};font-size:11px;margin-top:2px;display:block;">似然度 {lik:.0%}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
