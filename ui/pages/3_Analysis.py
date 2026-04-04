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

stock_list = [f"{w['stock_code']} - {w.get('name', '')}" for w in wl]
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
        
    with storage._get_conn() as conn:
        cursor = conn.execute("SELECT * FROM counter_evidence WHERE stock_code=?", (code,))
        ce_row = cursor.fetchone()
        ce_score = ce_row[1] if ce_row else 0
        ce_alert = ce_row[3] if ce_row else "NONE"
        ce_events = [] # 简化，实际应反序列化 history
        
        cursor = conn.execute("SELECT advice_type, confidence, summary, reasoning, trade_plan, key_watch_points, invalidation, alerts, generated_by FROM trade_advice WHERE stock_code=? ORDER BY updated_at DESC LIMIT 1", (code,))
        adv = cursor.fetchone()
        import json
        advice = {}
        if adv:
            advice = {
                "advice_type": adv[0],
                "confidence": adv[1],
                "summary": adv[2],
                "reasoning": adv[3],
                "trade_plan": json.loads(adv[4]) if adv[4] else {},
                "key_watch_points": json.loads(adv[5]) if adv[5] else [],
                "invalidation": adv[6],
                "alerts": json.loads(adv[7]) if adv[7] else [],
                "generated_by": adv[8]
            }
            
        cursor = conn.execute("SELECT * FROM signal_chain WHERE stock_code=? AND status='ACTIVE'", (code,))
        chain_row = cursor.fetchone()
        pct = chain_row[4] if chain_row else 0
        
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
        "signals": signals
    }

data = load_analysis_data(stock_code, force_run)

if data and not data["df"].empty:
    df = data["df"]
    st.title(f"🔬 {sel_stock} 深度分析")
    
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
