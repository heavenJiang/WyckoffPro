"""
ui/components/pnf_chart.py — 点数图(P&F)组件
"""
import streamlit as st
import plotly.graph_objects as go
import numpy as np


def render_pnf_chart(pnf_data, title="点数图 (P&F)"):
    """渲染点数图"""
    if not pnf_data or not pnf_data.columns:
        st.caption("暂无点数图数据")
        return

    st.markdown(f"#### {title}")
    
    # 提取点位
    x_vals = []
    y_vals = []
    text_vals = []
    colors = []
    
    for col_idx, col in enumerate(pnf_data.columns):
        for box in col:
            x_vals.append(col_idx)
            y_vals.append(box.value)
            text_vals.append(box.direction)
            colors.append("#2ecc71" if box.direction == "X" else "#e74c3c")
            
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=x_vals,
        y=y_vals,
        mode="text",
        text=text_vals,
        textfont=dict(color=colors, size=14, weight="bold"),
        hoverinfo="y",
    ))
    
    # 横向计数和目标线
    if getattr(pnf_data, 'count_target', 0) > 0:
        fig.add_hline(y=pnf_data.count_target, line_dash="dash", line_color="#f1c40f", 
                      annotation_text=f"计数目标: {pnf_data.count_target:.2f}")
        
    if getattr(pnf_data, 'base_low', 0) > 0:
        fig.add_hline(y=pnf_data.base_low, line_dash="dot", line_color="#7f8c8d", 
                      annotation_text=f"基础底: {pnf_data.base_low:.2f}")

    fig.update_layout(
        height=400,
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        xaxis=dict(showgrid=True, gridcolor="#262626", zeroline=False, dtick=1),
        yaxis=dict(showgrid=True, gridcolor="#262626", zeroline=False, dtick=pnf_data.box_size),
        margin=dict(l=40, r=40, t=30, b=20),
        showlegend=False,
        dragmode="pan",
    )
    
    st.plotly_chart(fig, use_container_width=True, config={
        "displayModeBar": True,
        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        "scrollZoom": True,
        "doubleClick": "reset",
    })
    _render_pnf_insight(pnf_data)


def _render_pnf_insight(pnf_data):
    """基于实际点数图数据生成动态走势解读"""
    if not pnf_data or not pnf_data.columns:
        return

    cols = pnf_data.columns
    last_col = cols[-1]
    col_count = len(cols)

    # ── 当前列方向 ──
    if last_col:
        cur_dir = last_col[0].direction
        cur_top = float(last_col[-1].value)
        cur_bot = float(last_col[0].value)
        col_len = len(last_col)
        if cur_dir == "X":
            dir_icon, dir_text, dir_color = "▲", f"当前为上涨列（X），共 {col_len} 格，最高 {cur_top:.2f}", "#2ecc71"
        else:
            dir_icon, dir_text, dir_color = "▼", f"当前为下跌列（O），共 {col_len} 格，最低 {cur_bot:.2f}", "#e74c3c"
    else:
        return

    # ── 横向计数目标 ──
    target = getattr(pnf_data, "count_target", 0) or 0
    base   = getattr(pnf_data, "base_low", 0) or 0
    box_sz = getattr(pnf_data, "box_size", 1) or 1
    current_price = cur_top if cur_dir == "X" else cur_bot

    if target > 0 and current_price > 0:
        dist_pct = (target - current_price) / current_price * 100
        if dist_pct > 0:
            target_text  = f"计数目标 {target:.2f}，距当前价格还有 {dist_pct:.1f}% 上涨空间（基础底 {base:.2f}）"
            target_color = "#f1c40f"
        else:
            target_text  = f"价格已超越计数目标 {target:.2f}，原目标已达成，关注是否出现派发信号"
            target_color = "#ef5350"
    else:
        target_text, target_color = "暂无有效横向计数目标（吸筹区宽度不足）", "#9ca3af"

    # ── 列数与结构判断 ──
    if col_count >= 10:
        x_cols = sum(1 for c in cols if c and c[0].direction == "X")
        o_cols = col_count - x_cols
        if x_cols > o_cols * 1.5:
            struct_text, struct_color = f"总列数 {col_count}，X列主导（{x_cols}X / {o_cols}O），整体偏多", "#2ecc71"
        elif o_cols > x_cols * 1.5:
            struct_text, struct_color = f"总列数 {col_count}，O列主导（{x_cols}X / {o_cols}O），整体偏空", "#e74c3c"
        else:
            struct_text, struct_color = f"总列数 {col_count}，X/O列均衡（{x_cols}X / {o_cols}O），方向不明朗", "#f39c12"
    else:
        struct_text, struct_color = f"数据列数较少（{col_count} 列），走势参考价值有限，建议扩大日期范围", "#9ca3af"

    # ── 渲染 ──
    rows = [
        f'<span style="color:{dir_color}">▪ <b>当前列</b> {dir_icon}　{dir_text}</span>',
        f'<span style="color:{target_color}">▪ <b>计数目标</b>　{target_text}</span>',
        f'<span style="color:{struct_color}">▪ <b>结构</b>　{struct_text}；箱格单位 {box_sz:.2f}</span>',
    ]
    body = "<br>".join(rows)
    st.markdown(f"""
<div style="background:#111827; border-left:3px solid #374151; padding:10px 14px;
            border-radius:0 4px 4px 0; font-size:12px; color:#9ca3af; margin-top:-8px;">
{body}
</div>
""", unsafe_allow_html=True)
