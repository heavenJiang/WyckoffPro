"""
ui/pages/5_Backtest.py
"""
import streamlit as st
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from main import storage, config, collector
from backtest.engine import BacktestEngine
from dataclasses import asdict
from datetime import datetime, timedelta

st.set_page_config(page_title="Backtest - WyckoffPro", page_icon="⏪", layout="wide")
st.title("⏪ 策略历史回测")

# ─── 顶部公共配置区 ───
wl = storage.get_watchlist()
stock_list = [f"{w['stock_code']} - {w.get('stock_name', '')}" for w in wl] if wl else []

with st.container(border=True):
    c_top1, c_top2 = st.columns([1, 2])
    with c_top1:
        sel_stock = st.selectbox("选择回测标固", stock_list, key="run_stock")
        code = sel_stock.split(" - ")[0] if sel_stock else ""
        name = sel_stock.split(" - ")[1] if sel_stock and " - " in sel_stock else code
        
        timeframe_map = {"日线": "daily", "周线": "weekly", "月线": "monthly", "小时线": "hourly"}
        def timeframe_changed():
            label = st.session_state.get("backtest_tf", "日线")
            tf = timeframe_map.get(label, "daily")
            now_dt = datetime.now()
            if tf == "daily":
                new_start = now_dt - timedelta(days=365 * 2)
            elif tf == "weekly":
                new_start = now_dt - timedelta(days=365 * 1)
            elif tf == "monthly":
                new_start = now_dt - timedelta(days=365 * 5)
            elif tf == "hourly":
                new_start = now_dt - timedelta(days=14)
            else:
                new_start = now_dt - timedelta(days=365)
            st.session_state["backtest_start"] = new_start.date()
            st.session_state["backtest_end"] = now_dt.date()

        sel_tf_label = st.radio("时间周期", list(timeframe_map.keys()), horizontal=True, key="backtest_tf", on_change=timeframe_changed)
        timeframe = timeframe_map[sel_tf_label]

    with c_top2:
        # 初始化日期
        if "backtest_start" not in st.session_state:
            st.session_state["backtest_start"] = datetime.now().date() - timedelta(days=365 * 2)
        if "backtest_end" not in st.session_state:
            st.session_state["backtest_end"] = datetime.now().date()

        st.write("时间范围选择")
        d_col1, d_col2 = st.columns(2)
        with d_col1:
            start_date = st.date_input("开始日期", key="backtest_start")
        with d_col2:
            end_date = st.date_input("结束日期", key="backtest_end")
        
        st.info(f"💡 当前配置: `{code} {name}` | `{sel_tf_label}` | `{start_date}` 至 `{end_date}`")

# ─── 数据预处理逻辑 ───
if code:
    df = storage.get_klines(code, timeframe, start_date=start_date.strftime("%Y-%m-%d"))
    if not df.empty:
        df = df[df["trade_date"] <= end_date.strftime("%Y-%m-%d")]
    data_ready = not df.empty
else:
    df = pd.DataFrame()
    data_ready = False

# ─── 功能分页 ───
tab_run, tab_data, tab_history = st.tabs(["🚀 策略回测", "📊 数据明细", "📜 回测库"])

def render_metrics_and_trades(metrics_data: dict, trades: list, duration: float = None):
    if duration:
        st.subheader(f"回测成绩单 (耗时: {duration}s)")
    else:
        st.subheader("回测成绩单")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("交易次数", metrics_data.get("total_trades", 0))
    c2.metric("胜率", f"{metrics_data.get('win_rate', 0)}%")
    c3.metric("总收益率", f"{metrics_data.get('total_return', 0)}%")
    c4.metric("最大回撤", f"{metrics_data.get('max_drawdown', 0)}%")
    
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("盈亏比", metrics_data.get("profit_factor", 0))
    c6.metric("平均盈利", f"{metrics_data.get('avg_win_pct', 0)}%")
    c7.metric("平均亏损", f"{metrics_data.get('avg_loss_pct', 0)}%")
    c8.metric("平均持仓(天/时)", metrics_data.get("avg_hold_days", 0))
    
    if trades:
        st.subheader("交易明细")
        t_df = pd.DataFrame(trades)
        st.dataframe(t_df, use_container_width=True)

with tab_run:
    if not data_ready:
        st.warning(f"本地数据库暂无 `{code}` 在选定范围内的数据。")
        if st.button("☁️ 从云端同步数据", key="sync_btn"):
            with st.spinner("同步中..."):
                df_cloud = collector.fetch_klines(code, timeframe, start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d"))
                if not df_cloud.empty:
                    storage.save_klines(code, df_cloud, timeframe)
                    st.success("同步完成，请刷新或再次操作")
                    st.rerun()
    else:
        all_signals = ["SC", "AR", "ST", "Spring", "SOS", "SOW", "UT", "UTAD", "JOC", "LPSY", "VDB", "BC", "PSY"]
        entry_signals = st.multiselect("触发入场的信号", all_signals, default=["Spring", "JOC"], key="run_sigs")
        
        if st.button("▶️ 运行回测", type="primary"):
            with st.spinner("回测引擎运行中..."):
                with storage._get_conn() as conn:
                    cursor = conn.execute(
                        "SELECT * FROM wyckoff_signal WHERE stock_code=? AND timeframe=? AND signal_date BETWEEN ? AND ?", 
                        (code, timeframe, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
                    )
                    cols = [description[0] for description in cursor.description]
                    signals = [dict(zip(cols, row)) for row in cursor.fetchall()]
                
                if not signals:
                    st.warning("选定时间段内未发现匹配的威科夫信号。")
                
                import time
                start_bt = time.time()
                engine = BacktestEngine(config)
                res = engine.run(code, df, signals, entry_signal_types=entry_signals)
                duration = round(time.time() - start_bt, 2)
                
                metrics_dict = asdict(res["metrics"])
                storage.save_backtest_result(code, timeframe, entry_signals, metrics_dict, res["trades"], stock_name=name)
                st.success("回测完成，版本已存入回测库。")
                render_metrics_and_trades(metrics_dict, res["trades"], duration)

with tab_data:
    if data_ready:
        st.subheader(f"📊 {code} {sel_tf_label} K 线明细")
        st.info(f"范围: {start_date} 至 {end_date} | 共 {len(df)} 条记录")
        st.dataframe(df, use_container_width=True, height=600)
    else:
        st.info("请先在回测选项中选择标的并确保数据已同步。")

with tab_history:
    st.subheader("🕰️ 历史回测版本记录")
    history = storage.get_backtest_history()
    if not history:
        st.info("暂无历史记录。")
    else:
        h_df = pd.DataFrame([
            {
                "ID": h["id"],
                "运行时间": h["run_at"],
                "代码": h["stock_code"],
                "名称": h["stock_name"],
                "周期": h["timeframe"],
                "胜率": f"{h['metrics'].get('win_rate')}%",
                "总收益": f"{h['metrics'].get('total_return')}%"
            } for h in history
        ])
        st.dataframe(h_df, use_container_width=True, hide_index=True)
        
        detail_options = {
            h["id"]: f"#{h['id']} | {h['run_at']} | {h['stock_code']} {h['stock_name']} ({h['timeframe']})"
            for h in history
        }
        sel_hist_id = st.selectbox("选择版本加载详情", options=list(detail_options.keys()), format_func=lambda x: detail_options.get(x, x))
        
        if sel_hist_id:
            detail = storage.get_backtest_detail(sel_hist_id)
            if detail:
                st.divider()
                st.info(f"版本详情: #{detail['id']} | {detail['stock_code']} | 周期: {detail['timeframe']}")
                render_metrics_and_trades(detail["metrics"], detail["trades"])

