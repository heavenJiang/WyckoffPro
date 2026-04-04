"""
ui/pages/5_Backtest.py
"""
import streamlit as st
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from main import storage, config
from backtest.engine import BacktestEngine

st.set_page_config(page_title="Backtest - WyckoffPro", page_icon="⏪")
st.title("⏪ 策略历史回测")

wl = storage.get_watchlist()
stock_list = [f"{w['stock_code']} - {w.get('name', '')}" for w in wl] if wl else []

col1, col2 = st.columns(2)
with col1:
    sel_stock = st.selectbox("选择回测标的", stock_list)
with col2:
    entry_signals = st.multiselect("触发入场的信号", ["Spring", "JOC", "SOS", "VDB"], default=["Spring", "JOC"])

if st.button("▶️ 运行回测", type="primary"):
    if not sel_stock:
        st.warning("请选择标的")
    else:
        code = sel_stock.split(" ")[0]
        st.write(f"正在准备 `{code}` 日线回测数据...")
        
        df = storage.get_klines(code, "daily", 500)
        
        with storage._get_conn() as conn:
            cursor = conn.execute("SELECT * FROM signal_log WHERE stock_code=?", (code,))
            cols = [description[0] for description in cursor.description]
            signals = [dict(zip(cols, row)) for row in cursor.fetchall()]
            
        if df.empty or not signals:
            st.error("数据不足或尚无信号纪录（请先执行全量数据收集）。")
        else:
            engine = BacktestEngine(config)
            res = engine.run(code, df, signals, entry_signal_types=entry_signals)
            
            # 显示结果
            metrics = res["metrics"]
            st.subheader("回测成绩单")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("交易次数", metrics.total_trades)
            c2.metric("胜率", f"{metrics.win_rate}%")
            c3.metric("总收益率", f"{metrics.total_return}%")
            c4.metric("最大回撤", f"{metrics.max_drawdown}%")
            
            c5, c6, c7, c8 = st.columns(4)
            c5.metric("盈亏比 (Profit Factor)", metrics.profit_factor)
            c6.metric("平均盈利", f"{metrics.avg_win_pct}%")
            c7.metric("平均亏损", f"{metrics.avg_loss_pct}%")
            c8.metric("平均持仓(天)", metrics.avg_hold_days)
            
            if res["trades"]:
                st.subheader("交易明细")
                t_df = pd.DataFrame(res["trades"])
                st.dataframe(t_df, use_container_width=True)
