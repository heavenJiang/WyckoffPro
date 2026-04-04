"""
ui/pages/3_Analysis.py
"""
import streamlit as st
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from main import storage, daily_analysis_pipeline, channel_analyzer, pnf_analyzer
from ui.components.kline_chart import render_kline_chart
from ui.components.pnf_chart import render_pnf_chart
from ui.components.signal_panel import render_signal_panel
from ui.components.advice_card import render_advice_card
from ui.components.counter_evidence_bar import render_counter_evidence_bar
from ui.components.phase_bar import render_phase_bar
import asyncio

st.set_page_config(page_title="Deep Analysis - WyckoffPro", page_icon="🔬", layout="wide")

wl = storage.get_watchlist()
if not wl:
    st.warning("自选股为空")
    st.stop()

stock_list = [f"{w['stock_code']} - {w.get('stock_name', '')}" for w in wl]
sel_stock = st.selectbox("选择分析标的", stock_list)

if not sel_stock:
    st.stop()
    
stock_code = sel_stock.split(" ")[0]

col_btn1, col_btn2 = st.columns([1, 5])
with col_btn1:
    force_run = st.button("🔄 刷新分析", type="primary")

@st.cache_data(ttl=300)
def load_analysis_data(code, force):
    # 如果强刷，则调用 pipeline
    if force:
        res = asyncio.run(daily_analysis_pipeline(code))
        if "error" in res:
            st.error(res["error"])
            return None
            
    # 从DB取数据
    df = storage.get_klines(code, "daily", 200)
    phase = storage.get_current_phase(code, "daily")
    if phase:
        from engine.phase_fsm import PhaseState
        ps = PhaseState(stock_code=code, **{k:v for k,v in phase.items() if k in ['phase_code', 'confidence', 'start_date', 'tr_upper', 'tr_lower', 'ice_line', 'creek_line', 'timeframe']})
    else:
        ps = None
        
    ce_data = storage.get_counter_evidence(code)
    ce_score = ce_data.get("current_score", 0) if ce_data else 0
    ce_alert = ce_data.get("alert_level", "NONE") if ce_data else "NONE"
    ce_events = ce_data.get("events", []) if ce_data else []
    
    advice = storage.get_latest_advice(code)
    if advice is None:
        advice = {}
        
    execution_meta = {}
    if force and 'res' in locals() and "execution_meta" in res:
        execution_meta = res["execution_meta"]
    else:
        # 尝试从日志中恢复最近一次的元数据
        logs = storage.get_falsification_history(code, limit=1)
        if logs:
            import json
            detail = json.loads(logs[0]["detail"]) if isinstance(logs[0]["detail"], str) else logs[0]["detail"]
            # 我们之前没在 log 里存 execution_meta，但在这次任务中我会让 pipeline 返回它
            # 如果没有，就显示基本信息
            execution_meta = {
                "end_time": logs[0]["executed_at"],
                "total_duration": "N/A (Historical)",
                "steps": []
            }
            
    with storage._get_conn() as conn:
        cursor = conn.execute("SELECT * FROM signal_chain WHERE stock_code=? AND status='ACTIVE'", (code,))
        chain_row = cursor.fetchone()
        pct = chain_row["completion_pct"] if chain_row else 0
        
    # TODO signals list
    signals = []
    
    return {
        "df": df,
        "phase_state": ps,
        "ce_score": ce_score,
        "ce_alert": ce_alert,
        "ce_events": ce_events,
        "advice": advice,
        "chain_pct": pct,
        "execution_meta": execution_meta,
        "signals": signals
    }

data = load_analysis_data(stock_code, force_run)

if data and not data["df"].empty:
    df = data["df"]
    # 提取代码和名称用于显示
    display_name = sel_stock # 格式通常是 "600000.SH - 浦发银行"
    st.title(f"🔬 {display_name} 深度技术分析")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # K线图
        channel = channel_analyzer.analyze(df, getattr(data["phase_state"], 'tr_upper', 0) if data["phase_state"] else 0, getattr(data["phase_state"], 'tr_lower', 0) if data["phase_state"] else 0)
        render_kline_chart(df, signals=data["signals"], phase_state=data["phase_state"], channel=channel, height=650)
        
        st.divider()
        # 点数图
        pnf = pnf_analyzer.build(df)
        render_pnf_chart(pnf)
        
    with col2:
        # 建议
        if data["advice"]:
            render_advice_card(data["advice"])
            
        # 阶段
        phase_code = getattr(data["phase_state"], 'phase_code', 'UNKNOWN') if data["phase_state"] else 'UNKNOWN'
        conf = getattr(data["phase_state"], 'confidence', 0) if data["phase_state"] else 0
        render_phase_bar(phase_code, conf)
        
        # 反面积分
        render_counter_evidence_bar(data["ce_score"], data["ce_alert"], data["ce_events"])
        
        # 信号和链
        st.metric("信号链完成度", f"{data['chain_pct']}%")
        if data["signals"]:
            render_signal_panel(data["signals"])

    # 🚀 执行元数据 (全宽显示在底部)
    st.divider()
    meta = data.get("execution_meta", {})
    if meta:
        with st.expander("🚀 分析执行元数据与性能指标"):
            st.info(f"分析流在 {meta.get('start_time')} 启动，总执行耗时: **{meta.get('total_duration')}s**")
            
            # 显示详细步骤表格
            steps = meta.get("steps", [])
            if steps:
                st.write("各步骤执行明细：")
                steps_df = pd.DataFrame(steps)
                st.dataframe(steps_df, use_container_width=True, hide_index=True)
    elif force_run:
         st.info("正在执行分析，请稍候...")
    else:
        st.caption("暂无执行元数据（请点击 '刷新分析' 获取实时指标）")

else:
    st.warning("数据加载失败，请检查数据库或重试。")
