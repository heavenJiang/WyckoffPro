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
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
