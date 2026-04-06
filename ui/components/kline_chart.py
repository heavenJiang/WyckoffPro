"""
ui/components/kline_chart.py — K线图组件（Plotly）
含阶段色带、信号标记、通道线。
"""
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np


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
            # 合并价格数据，统一处理
            sig_df = sig_df.merge(
                df[["trade_date", "low", "high"]],
                left_on="signal_date", right_on="trade_date", how="left"
            ).dropna(subset=["low", "high"])

            BUY_SIDE = {"SC", "Spring", "AR", "ST", "SOS", "VDB", "JOC"}

            # 按日期+信号类型排序，保证同天多信号偏移顺序固定
            sig_df = sig_df.sort_values(["signal_date", "signal_type"]).reset_index(drop=True)

            # 记录每个(日期, 方向)已放置的信号数，用于逐步偏移
            _slot: dict = {}
            y_positions = []
            for _, row in sig_df.iterrows():
                date = str(row["signal_date"])
                is_buy = row["signal_type"] in BUY_SIDE
                key = (date, is_buy)
                n = _slot.get(key, 0)
                _slot[key] = n + 1
                step = 0.014 * n          # 每多一个信号偏移1.4%
                if is_buy:
                    y_positions.append(float(row["low"]) * (0.995 - step))
                else:
                    y_positions.append(float(row["high"]) * (1.005 + step))
            sig_df["_y"] = y_positions

            # 按信号类型分组渲染（legend显示）
            for sig_type, sub in sig_df.groupby("signal_type"):
                color = SIGNAL_COLORS.get(sig_type, "#ffffff")
                is_buy = sig_type in BUY_SIDE
                fig.add_trace(go.Scatter(
                    x=sub["signal_date"],
                    y=sub["_y"],
                    mode="markers+text",
                    marker=dict(
                        color=color, size=10,
                        symbol="triangle-up" if is_buy else "triangle-down",
                    ),
                    text=[sig_type] * len(sub),
                    textposition="bottom center" if is_buy else "top center",
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
    # 默认显示最近 120 根 K 线，用户可拖动查看更早数据
    n_total = len(df)
    n_default = min(120, n_total)
    x_range = [n_total - n_default - 0.5, n_total - 0.5]

    fig.update_layout(
        height=height,
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font=dict(color="#e0e0e0"),
        showlegend=True,
        legend=dict(
            bgcolor="#1a1a2e", bordercolor="#444",
            x=0.01, y=0.99,
            font=dict(size=10)
        ),
        margin=dict(l=40, r=40, t=30, b=20),
        dragmode="pan",   # 拖动=平移，滚轮=缩放
        # category 轴：消除非交易日空隙，三图保持同步
        xaxis=dict(
            type="category",
            range=x_range,
            rangeslider=dict(visible=False),
            gridcolor="#262626", zeroline=False,
            showspikes=True, spikecolor="#555",
            tickangle=-45, nticks=12,
        ),
        xaxis2=dict(
            type="category",
            range=x_range,
            rangeslider=dict(visible=False),
            gridcolor="#262626", zeroline=False,
            showspikes=True, spikecolor="#555",
        ),
        xaxis3=dict(
            type="category",
            range=x_range,
            rangeslider=dict(visible=False),
            gridcolor="#262626", zeroline=False,
            showspikes=True, spikecolor="#555",
        ),
    )
    for i in range(1, 4):
        fig.update_yaxes(gridcolor="#262626", zeroline=False, row=i, col=1)

    st.plotly_chart(fig, use_container_width=True, config={
        "displayModeBar": True,
        "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
        "scrollZoom": True,
        "doubleClick": "reset",
    })
    _render_kline_insight(df, signals, phase_state, channel)


def _render_kline_insight(df: pd.DataFrame, signals, phase_state, channel):
    """基于实际数据动态生成图表走势解读"""

    last   = df.iloc[-1]
    close  = float(last.get("close", 0) or 0)
    volume = float(last.get("volume", 0) or 0)

    ma20_series = df["close"].rolling(20, min_periods=5).mean()
    ma20 = float(ma20_series.iloc[-1]) if not ma20_series.empty and not pd.isna(ma20_series.iloc[-1]) else None
    vol_avg20 = float(df["volume"].tail(20).mean()) if len(df) >= 5 else 0

    # ── K线趋势判断 ──
    if ma20 and ma20 > 0:
        diff_pct = (close - ma20) / ma20 * 100
        if diff_pct > 2:
            trend_icon, trend_text, trend_color = "↑", f"多头结构：收盘价 {close:.2f} 高于 MA20（{ma20:.2f}）{diff_pct:.1f}%，上升趋势", "#2ecc71"
        elif diff_pct < -2:
            trend_icon, trend_text, trend_color = "↓", f"空头结构：收盘价 {close:.2f} 低于 MA20（{ma20:.2f}）{abs(diff_pct):.1f}%，下降趋势", "#e74c3c"
        else:
            trend_icon, trend_text, trend_color = "→", f"震荡结构：收盘价 {close:.2f} 贴近 MA20（{ma20:.2f}），方向待确认", "#f39c12"
    else:
        trend_icon, trend_text, trend_color = "—", "数据不足，无法判断趋势", "#888"

    # ── 成交量分析 ──
    if vol_avg20 > 0:
        vol_ratio = volume / vol_avg20
        if vol_ratio >= 2.0:
            vol_icon, vol_text, vol_color = "🔥", f"显著放量（{vol_ratio:.1f}x 均量），需结合价格方向判断主动性", "#ef5350"
        elif vol_ratio >= 1.3:
            vol_icon, vol_text, vol_color = "📈", f"温和放量（{vol_ratio:.1f}x 均量），量价配合需观察", "#f39c12"
        elif vol_ratio <= 0.5:
            vol_icon, vol_text, vol_color = "💧", f"明显缩量（{vol_ratio:.1f}x 均量），观望情绪浓，可能为 VDB 蓄力信号", "#26a69a"
        else:
            vol_icon, vol_text, vol_color = "📊", f"量能正常（{vol_ratio:.1f}x 均量），无异常放缩量", "#9ca3af"
    else:
        vol_icon, vol_text, vol_color = "—", "成交量数据不足", "#888"

    # ── ATR 分析 ──
    atr_text, atr_color = "", "#9ca3af"
    if "atr_20" in df.columns:
        atr_last = float(last.get("atr_20", 0) or 0)
        atr_avg  = float(df["atr_20"].tail(60).mean()) if len(df) >= 10 else 0
        if atr_last > 0 and atr_avg > 0:
            atr_ratio = atr_last / atr_avg
            if atr_ratio > 1.4:
                atr_text  = f"ATR 偏高（{atr_last:.2f}，近期均值 {atr_avg:.2f}），波动加剧，注意仓位控制"
                atr_color = "#ef5350"
            elif atr_ratio < 0.65:
                atr_text  = f"ATR 收缩（{atr_last:.2f}，近期均值 {atr_avg:.2f}），波动蓄力，可能为弹簧/蓄积前兆"
                atr_color = "#2ecc71"
            else:
                atr_text  = f"ATR 正常（{atr_last:.2f}），波动处于常规水平"

    # ── 通道位置 ──
    channel_text, channel_color = "", "#9ca3af"
    if channel:
        sup = getattr(channel, "support_1", 0) or 0
        res = getattr(channel, "resistance_1", 0) or 0
        if sup > 0 and res > sup:
            pos_pct = (close - sup) / (res - sup) * 100
            if pos_pct >= 80:
                channel_text  = f"价格处于通道上部（{pos_pct:.0f}%），接近阻力 {res:.2f}，注意压力"
                channel_color = "#ef5350"
            elif pos_pct <= 20:
                channel_text  = f"价格处于通道下部（{pos_pct:.0f}%），接近支撑 {sup:.2f}，关注止跌信号"
                channel_color = "#26a69a"
            else:
                channel_text  = f"价格居于通道中部（{pos_pct:.0f}%），支撑 {sup:.2f} / 阻力 {res:.2f}"

    # ── 近期信号摘要 ──
    sig_text = ""
    if signals:
        recent = sorted(signals, key=lambda s: s.get("signal_date", ""), reverse=True)[:3]
        parts = [f"{s['signal_type']}（{s.get('signal_date','')[:10]}，{s.get('likelihood',0):.0%}）"
                 for s in recent]
        sig_text = "近期信号：" + " · ".join(parts)

    # ── 渲染说明框 ──
    rows = [
        f'<span style="color:{trend_color}">▪ <b>趋势</b> {trend_icon}　{trend_text}</span>',
        f'<span style="color:{vol_color}">▪ <b>量能</b> {vol_icon}　{vol_text}</span>',
    ]
    if atr_text:
        rows.append(f'<span style="color:{atr_color}">▪ <b>波幅</b>　{atr_text}</span>')
    if channel_text:
        rows.append(f'<span style="color:{channel_color}">▪ <b>通道</b>　{channel_text}</span>')
    if sig_text:
        rows.append(f'<span style="color:#ab47bc">▪ <b>信号</b>　{sig_text}</span>')

    body = "<br>".join(rows)
    st.markdown(f"""
<div style="background:#111827; border-left:3px solid #374151; padding:10px 14px;
            border-radius:0 4px 4px 0; font-size:12px; color:#9ca3af; margin-top:-8px;">
{body}
</div>
""", unsafe_allow_html=True)
