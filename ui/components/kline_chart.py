"""
ui/components/kline_chart.py — K线图组件（Plotly）
含阶段色带、信号标记、通道线。
"""
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd


PHASE_COLORS = {
    "MKD": "rgba(231,76,60,0.12)",
    "ACC-A": "rgba(230,126,34,0.12)",
    "ACC-B": "rgba(243,156,18,0.12)",
    "ACC-C": "rgba(241,196,15,0.12)",
    "ACC-D": "rgba(46,204,113,0.12)",
    "ACC-E": "rgba(39,174,96,0.12)",
    "MKU": "rgba(0,188,212,0.12)",
    "DIS-A": "rgba(52,152,219,0.12)",
    "DIS-B": "rgba(155,89,182,0.12)",
    "DIS-C": "rgba(142,68,173,0.12)",
    "DIS-D": "rgba(192,57,43,0.12)",
    "TR_UNDETERMINED": "rgba(149,165,166,0.08)",
}

SIGNAL_COLORS = {
    "SC": "#e74c3c", "AR": "#e67e22", "ST": "#f39c12", "Spring": "#2ecc71",
    "SOS": "#27ae60", "SOW": "#c0392b", "UT": "#8e44ad", "UTAD": "#6c3483",
    "JOC": "#00bcd4", "LPSY": "#e91e63", "VDB": "#4caf50", "BC": "#3498db", "PSY": "#9b59b6",
}


def render_kline_chart(df: pd.DataFrame, signals: list = None, phase_state=None,
                       channel=None, phase_history: list = None, height: int = 600):
    """渲染交互式K线图"""
    if df.empty:
        st.warning("无K线数据")
        return

    fig = make_subplots(
        rows=3, cols=1,
        row_heights=[0.65, 0.20, 0.15],
        shared_xaxes=True,
        vertical_spacing=0.02,
        subplot_titles=("K线图", "成交量", "ATR-20")
    )

    # ── 阶段色带背景 ──
    if phase_history:
        for ph in phase_history:
            bg_color = PHASE_COLORS.get(ph.get("phase_code", ""), "rgba(0,0,0,0)")
            s = ph.get("start_date", "")
            e = ph.get("end_date") or df["trade_date"].iloc[-1]
            if s:
                fig.add_vrect(x0=s, x1=e, fillcolor=bg_color, line_width=0,
                              row=1, col=1)

    # ── K线 ──
    fig.add_trace(go.Candlestick(
        x=df["trade_date"],
        open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        name="K线",
        increasing_line_color="#26a69a",
        decreasing_line_color="#ef5350",
    ), row=1, col=1)

    # ── MA20 ──
    ma20 = df["close"].rolling(20, min_periods=5).mean()
    fig.add_trace(go.Scatter(
        x=df["trade_date"], y=ma20, mode="lines",
        line=dict(color="#ffa726", width=1.5),
        name="MA20", opacity=0.8
    ), row=1, col=1)

    # ── 通道线 ──
    if channel:
        for attr, color, label in [
            ("upper", "#ef5350", "通道上轨"),
            ("lower", "#26a69a", "通道下轨"),
            ("creek_line", "#ffd700", "Creek"),
            ("ice_line", "#00bcd4", "Ice"),
        ]:
            val = getattr(channel, attr, 0)
            if val and val > 0:
                fig.add_hline(y=val, line_color=color, line_width=1, line_dash="dash",
                              annotation_text=f"{label}:{val:.2f}",
                              annotation_font_size=10, row=1, col=1)

    # ── TR区间 ──
    if phase_state and getattr(phase_state, "tr_upper", 0) and getattr(phase_state, "tr_lower", 0):
        fig.add_hrect(
            y0=phase_state.tr_lower, y1=phase_state.tr_upper,
            fillcolor="rgba(255,255,255,0.04)", line_color="#555",
            line_width=1, row=1, col=1
        )

    # ── 信号标记 ──
    if signals:
        sig_df = pd.DataFrame(signals)
        if not sig_df.empty:
            for sig_type in sig_df["signal_type"].unique():
                sub = sig_df[sig_df["signal_type"] == sig_type]
                color = SIGNAL_COLORS.get(sig_type, "#ffffff")
                # 与K线数据做连接获取价格
                sub_merged = sub.merge(
                    df[["trade_date", "low", "high"]],
                    left_on="signal_date", right_on="trade_date", how="left"
                )
                y_pos = sub_merged["low"] * 0.995 if sig_type in ("SC", "Spring", "AR", "ST", "SOS", "VDB") \
                    else sub_merged["high"] * 1.005
                fig.add_trace(go.Scatter(
                    x=sub_merged["signal_date"],
                    y=y_pos,
                    mode="markers+text",
                    marker=dict(color=color, size=10, symbol="triangle-up" if sig_type in ("Spring", "SOS", "JOC") else "triangle-down"),
                    text=[sig_type] * len(sub_merged),
                    textposition="bottom center",
                    textfont=dict(size=9, color=color),
                    name=sig_type,
                ), row=1, col=1)

    # ── 成交量 ──
    colors = ["#26a69a" if c >= o else "#ef5350" for c, o in zip(df["close"], df["open"])]
    fig.add_trace(go.Bar(
        x=df["trade_date"], y=df["volume"],
        marker_color=colors, name="成交量", opacity=0.7
    ), row=2, col=1)

    # ── ATR ──
    if "atr_20" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["trade_date"], y=df["atr_20"],
            mode="lines", line=dict(color="#ab47bc", width=1.5),
            name="ATR-20"
        ), row=3, col=1)

    # ── 布局 ──
    fig.update_layout(
        height=height,
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font=dict(color="#e0e0e0"),
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(
            bgcolor="#1a1a2e", bordercolor="#444",
            x=0.01, y=0.99,
            font=dict(size=10)
        ),
        margin=dict(l=40, r=40, t=30, b=20),
    )
    for i in range(1, 4):
        fig.update_xaxes(
            gridcolor="#262626", zeroline=False, row=i, col=1,
            showspikes=True, spikecolor="#555"
        )
        fig.update_yaxes(
            gridcolor="#262626", zeroline=False, row=i, col=1
        )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
