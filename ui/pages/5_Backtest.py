"""
ui/pages/5_Backtest.py — 策略历史回测
"""
import streamlit as st
import sys, os, time
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from dataclasses import asdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from main import storage, config, collector
from ui.components.glossary import tip
from ui.components.translations import CN
from backtest.engine import BacktestEngine

st.set_page_config(page_title="Backtest - WyckoffPro", page_icon="⏪", layout="wide")
st.title("⏪ 策略历史回测")

# ══════════════════════════════════════════════════════════
# 顶部：标的 & 时间配置
# ══════════════════════════════════════════════════════════
wl = storage.get_watchlist()
stock_list = [f"{w['stock_code']} - {w.get('stock_name', '')}" for w in wl] if wl else []

TF_MAP     = {"日线": "daily", "周线": "weekly", "月线": "monthly"}
TF_DEFAULT = {"日线": 365 * 3, "周线": 365 * 5, "月线": 365 * 10}

with st.container(border=True):
    c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])
    with c1:
        sel_stock = st.selectbox("回测标的", stock_list, key="bt_stock")
        code = sel_stock.split(" - ")[0] if sel_stock else ""
        name = sel_stock.split(" - ")[1] if sel_stock and " - " in sel_stock else code
    with c2:
        sel_tf_label = st.selectbox("周期", list(TF_MAP), key="bt_tf")
        timeframe = TF_MAP[sel_tf_label]
    with c3:
        if "bt_start" not in st.session_state:
            st.session_state["bt_start"] = datetime.now().date() - timedelta(days=TF_DEFAULT[sel_tf_label])
        start_date = st.date_input("开始日期", key="bt_start")
    with c4:
        if "bt_end" not in st.session_state:
            st.session_state["bt_end"] = datetime.now().date()
        end_date = st.date_input("结束日期", key="bt_end")
    with c5:
        st.caption("资金")
        init_cap = st.number_input("初始资金(万)", min_value=1, max_value=10000,
                                   value=10, step=1, key="bt_cap")

# ══════════════════════════════════════════════════════════
# 数据加载
# ══════════════════════════════════════════════════════════
if code:
    df = storage.get_klines(code, timeframe,
                            start_date=start_date.strftime("%Y-%m-%d"))
    if not df.empty:
        df = df[df["trade_date"] <= end_date.strftime("%Y-%m-%d")]
    data_ready = not df.empty
else:
    df = pd.DataFrame()
    data_ready = False

# ══════════════════════════════════════════════════════════
# Tab 布局
# ══════════════════════════════════════════════════════════
tab_run, tab_data, tab_history = st.tabs(["🚀 策略回测", "📊 数据明细", "📜 历史记录"])

# ────────────────────────────────────────────────────────
# Tab 1: 策略回测
# ────────────────────────────────────────────────────────
ALL_SIGNALS = ["SC", "AR", "ST", "Spring", "SOS", "SOW",
               "UT", "UTAD", "JOC", "LPSY", "VDB", "BC", "PSY"]
ENTRY_DEFAULT = ["Spring", "JOC", "SOS"]
EXIT_DEFAULT  = ["SOW", "LPSY", "UTAD"]

with tab_run:
    if not data_ready:
        st.warning(f"本地数据库暂无 `{code}` 在选定范围内的数据。")
        if st.button("☁️ 同步数据", key="sync_btn"):
            with st.spinner("同步中..."):
                df_c = collector.fetch_klines(code, timeframe,
                                              start_date.strftime("%Y%m%d"),
                                              end_date.strftime("%Y%m%d"))
                if not df_c.empty:
                    storage.save_klines(code, df_c, timeframe)
                    st.success("同步完成，请刷新")
                    st.rerun()
    else:
        # ── 策略参数 ──────────────────────────────────────────────
        with st.container(border=True):
            st.markdown("**策略参数配置**")
            pa, pb, pc = st.columns(3)

            with pa:
                st.markdown("**入场信号**")
                entry_sigs = st.multiselect(
                    "触发买入的信号",
                    options=ALL_SIGNALS,
                    default=ENTRY_DEFAULT,
                    format_func=lambda x: f"{CN.signal(x)} ({x})",
                    key="bt_entry",
                )
                min_lik = st.slider("最低似然度", 0.4, 0.9, 0.55, 0.05,
                                    key="bt_lik", help="信号可信度阈值，低于此值忽略")

            with pb:
                st.markdown("**退出信号**")
                exit_sigs = st.multiselect(
                    "触发卖出的信号（可选）",
                    options=ALL_SIGNALS,
                    default=EXIT_DEFAULT,
                    format_func=lambda x: f"{CN.signal(x)} ({x})",
                    key="bt_exit",
                    help="出现这些信号时主动平仓，优先级高于止损/止盈",
                )

            with pc:
                st.markdown("**止损 & 盈亏比**")
                stop_type = st.radio("止损类型", ["ATR倍数", "固定%", "近期低点"],
                                     horizontal=True, key="bt_stop_type")
                if stop_type == "ATR倍数":
                    atr_mult = st.slider("ATR倍数", 1.0, 4.0, 2.0, 0.5, key="bt_atr")
                    stop_pct = 5.0
                elif stop_type == "固定%":
                    stop_pct = st.slider("止损%", 2.0, 15.0, 5.0, 0.5, key="bt_spct")
                    atr_mult = 2.0
                else:
                    atr_mult, stop_pct = 2.0, 5.0
                rr = st.slider("盈亏比 (RR)", 1.0, 5.0, 2.0, 0.5, key="bt_rr",
                               help="目标价 = 入场价 + 止损距离 × RR")

        run_btn = st.button("▶️ 运行回测", type="primary", key="bt_run")

        if run_btn:
            if not entry_sigs:
                st.error("请至少选择一种入场信号。")
                st.stop()

            with st.spinner("回测引擎运行中…"):
                with storage._get_conn() as conn:
                    rows = conn.execute(
                        "SELECT * FROM wyckoff_signal "
                        "WHERE stock_code=? AND timeframe=? "
                        "AND signal_date BETWEEN ? AND ?",
                        (code, timeframe,
                         start_date.strftime("%Y-%m-%d"),
                         end_date.strftime("%Y-%m-%d"))
                    ).fetchall()
                    signals = [dict(r) for r in rows]

                if not signals:
                    st.warning("选定时间段内无威科夫信号。建议先在 Analysis 页对该标的运行分析以生成信号。")
                    st.stop()

                STOP_TYPE_MAP = {"ATR倍数": "atr", "固定%": "pct", "近期低点": "low"}
                t0 = time.time()
                engine = BacktestEngine(config)
                engine.initial_capital = init_cap * 10_000
                res = engine.run(
                    code, df, signals,
                    entry_signal_types=entry_sigs,
                    exit_signal_types=exit_sigs,
                    stop_type=STOP_TYPE_MAP[stop_type],
                    stop_atr_mult=atr_mult,
                    stop_pct=stop_pct,
                    target_rr=rr,
                    min_likelihood=min_lik,
                )
                duration = round(time.time() - t0, 2)

                m  = asdict(res["metrics"])
                storage.save_backtest_result(
                    code, timeframe, entry_sigs, m, res["trades"], stock_name=name
                )
                st.session_state[f"bt_result_{code}"] = res
                st.success(f"回测完成（{duration}s），版本已存入历史记录。")

        # ── 展示结果 ──────────────────────────────────────────────
        res = st.session_state.get(f"bt_result_{code}")
        if res:
            m      = asdict(res["metrics"])
            trades = res["trades"]

            # 绩效指标
            st.divider()
            st.markdown("### 📊 回测绩效")
            mc1, mc2, mc3, mc4, mc5, mc6 = st.columns(6)
            mc1.metric("交易次数",   m.get("total_trades", 0))
            mc2.metric("胜率",       f"{m.get('win_rate', 0)}%", help=tip("胜率"))
            mc3.metric("总收益率",   f"{m.get('total_return', 0)}%",
                       delta=f"年化 {m.get('annualized_return', 0)}%")
            mc4.metric("最大回撤",   f"{m.get('max_drawdown', 0)}%", help=tip("最大回撤"))
            mc5.metric("盈亏比",     m.get("profit_factor", 0), help=tip("Profit Factor"))
            mc6.metric("Sharpe",     m.get("sharpe_ratio", 0))

            ma1, ma2, ma3 = st.columns(3)
            ma1.metric("平均盈利",   f"{m.get('avg_win_pct', 0)}%")
            ma2.metric("平均亏损",   f"{m.get('avg_loss_pct', 0)}%")
            ma3.metric("平均持仓天", m.get("avg_hold_days", 0))

            # ── 图表区 ─────────────────────────────────────────────
            st.divider()
            fig_col, eq_col = st.columns(2)

            # K线 + 买卖标记
            with fig_col:
                st.markdown("**K线图 · 买卖信号标记**")
                buy_m  = res.get("buy_markers", [])
                sell_m = res.get("sell_markers", [])

                # 最多显示最近 300 根，避免图太密
                df_plot = df.tail(300).copy()
                fig_k = go.Figure()
                fig_k.add_trace(go.Candlestick(
                    x=df_plot["trade_date"],
                    open=df_plot["open"], high=df_plot["high"],
                    low=df_plot["low"],   close=df_plot["close"],
                    name="K线",
                    increasing_line_color="#ef5350",
                    decreasing_line_color="#26a69a",
                ))

                if buy_m:
                    bdf = pd.DataFrame(buy_m)
                    fig_k.add_trace(go.Scatter(
                        x=bdf["date"], y=bdf["price"],
                        mode="markers+text",
                        marker=dict(symbol="triangle-up", size=12,
                                    color="#00e676", line=dict(color="#fff", width=1)),
                        text=bdf["signal"].map(CN.signal),
                        textposition="bottom center",
                        textfont=dict(size=9, color="#00e676"),
                        name="买入",
                    ))
                if sell_m:
                    sdf = pd.DataFrame(sell_m)
                    _reason_cn = {"STOP_LOSS": "止损", "TARGET": "止盈",
                                  "SIGNAL": "信号", "END_OF_DATA": "结束"}
                    fig_k.add_trace(go.Scatter(
                        x=sdf["date"], y=sdf["price"],
                        mode="markers+text",
                        marker=dict(symbol="triangle-down", size=12,
                                    color="#ff5252", line=dict(color="#fff", width=1)),
                        text=sdf["reason"].map(lambda r: _reason_cn.get(r, r)),
                        textposition="top center",
                        textfont=dict(size=9, color="#ff5252"),
                        name="卖出",
                    ))

                fig_k.update_layout(
                    height=360, xaxis_rangeslider_visible=False,
                    margin=dict(l=0, r=0, t=8, b=0),
                    plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                    font=dict(color="#fafafa", size=10),
                    legend=dict(orientation="h", y=1.06, x=0),
                    xaxis=dict(gridcolor="#1e2533", type="category",
                               tickangle=-45, nticks=10),
                    yaxis=dict(gridcolor="#1e2533"),
                )
                st.plotly_chart(fig_k, use_container_width=True)

            # 净值曲线 vs 基准（持股不动）
            with eq_col:
                st.markdown("**净值曲线 vs 买入持有基准**")
                eq_data = res.get("equity_curve", [])
                if eq_data:
                    eq_df = pd.DataFrame(eq_data)
                    fig_eq = go.Figure()
                    fig_eq.add_trace(go.Scatter(
                        x=eq_df["date"], y=eq_df["equity"] / (init_cap * 10_000) * 100,
                        name="策略净值%",
                        line=dict(color="#42a5f5", width=2),
                        fill="tozeroy", fillcolor="rgba(66,165,245,0.06)",
                    ))
                    fig_eq.add_trace(go.Scatter(
                        x=eq_df["date"], y=eq_df["benchmark"] / (init_cap * 10_000) * 100,
                        name="持股不动%",
                        line=dict(color="#9e9e9e", width=1.5, dash="dot"),
                    ))
                    # 持仓区间背景
                    in_pos = eq_df[eq_df["in_position"]]
                    if not in_pos.empty:
                        for _, grp in in_pos.groupby(
                            (in_pos["in_position"] != in_pos["in_position"].shift()).cumsum()
                        ):
                            fig_eq.add_vrect(
                                x0=grp["date"].iloc[0], x1=grp["date"].iloc[-1],
                                fillcolor="rgba(66,165,245,0.06)", line_width=0,
                            )
                    fig_eq.add_hline(y=100, line_dash="dot",
                                     line_color="#555", line_width=1)
                    fig_eq.update_layout(
                        height=360,
                        margin=dict(l=0, r=0, t=8, b=0),
                        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                        font=dict(color="#fafafa", size=10),
                        legend=dict(orientation="h", y=1.06, x=0),
                        xaxis=dict(gridcolor="#1e2533", type="category",
                                   tickangle=-45, nticks=10),
                        yaxis=dict(gridcolor="#1e2533",
                                   title="净值（初始=100）"),
                    )
                    st.plotly_chart(fig_eq, use_container_width=True)

            # ── 交易明细 ──────────────────────────────────────────
            if trades:
                st.divider()
                st.markdown("**交易明细**")
                _exit_cn = {"STOP_LOSS": "止损", "TARGET": "止盈",
                            "SIGNAL": "信号平仓", "END_OF_DATA": "数据结束"}
                t_df = pd.DataFrame(trades)
                t_df = t_df.rename(columns={
                    "signal_type":  "信号",
                    "open_date":    "买入日",
                    "close_date":   "卖出日",
                    "entry_price":  "买入价",
                    "exit_price":   "卖出价",
                    "stop_loss":    "止损价",
                    "target":       "目标价",
                    "shares":       "股数",
                    "pnl_amount":   "盈亏金额",
                    "pnl_pct":      "盈亏%",
                    "exit_reason":  "退出原因",
                    "hold_days":    "持仓天",
                })
                if "信号" in t_df.columns:
                    t_df["信号"] = t_df["信号"].map(
                        lambda x: f"{CN.signal(x)} ({x})"
                    )
                if "退出原因" in t_df.columns:
                    t_df["退出原因"] = t_df["退出原因"].map(
                        lambda r: _exit_cn.get(r, r)
                    )
                if "stock_code" in t_df.columns:
                    t_df = t_df.drop(columns=["stock_code"])
                st.dataframe(
                    t_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "盈亏%": st.column_config.NumberColumn(
                            "盈亏%", format="%.2f%%",
                            help="单笔盈亏（不含手续费摊销）"
                        ),
                        "盈亏金额": st.column_config.NumberColumn("盈亏金额", format="¥%.0f"),
                    },
                )

# ────────────────────────────────────────────────────────
# Tab 2: 数据明细
# ────────────────────────────────────────────────────────
with tab_data:
    if data_ready:
        st.subheader(f"📊 {code} {sel_tf_label} K 线明细")
        st.caption(f"{start_date} 至 {end_date} | 共 {len(df)} 条")
        st.dataframe(df, use_container_width=True, height=600)
    else:
        st.info("请先选择标的并确保数据已同步。")

# ────────────────────────────────────────────────────────
# Tab 3: 历史记录
# ────────────────────────────────────────────────────────
with tab_history:
    st.subheader("🕰️ 历史回测记录")
    history = storage.get_backtest_history()
    if not history:
        st.info("暂无历史记录。")
    else:
        h_df = pd.DataFrame([{
            "ID":     h["id"],
            "时间":   h["run_at"][:16],
            "代码":   h["stock_code"],
            "名称":   h["stock_name"],
            "周期":   CN.timeframe(h["timeframe"]),
            "交易次": h["metrics"].get("total_trades", 0),
            "胜率":   f"{h['metrics'].get('win_rate', 0)}%",
            "总收益": f"{h['metrics'].get('total_return', 0)}%",
            "年化收益": f"{h['metrics'].get('annualized_return', 0)}%",
            "最大回撤": f"{h['metrics'].get('max_drawdown', 0)}%",
            "Sharpe": h["metrics"].get("sharpe_ratio", 0),
        } for h in history])
        st.dataframe(h_df, use_container_width=True, hide_index=True)

        st.divider()
        detail_opts = {
            h["id"]: f"#{h['id']} | {h['run_at'][:16]} | {h['stock_code']} {h['stock_name']} ({CN.timeframe(h['timeframe'])})"
            for h in history
        }
        sel_id = st.selectbox("查看详情",
                              options=list(detail_opts.keys()),
                              format_func=lambda x: detail_opts.get(x, x))
        if sel_id:
            detail = storage.get_backtest_detail(sel_id)
            if detail:
                dm = detail["metrics"]
                d1, d2, d3, d4, d5, d6 = st.columns(6)
                d1.metric("交易次数", dm.get("total_trades", 0))
                d2.metric("胜率",     f"{dm.get('win_rate', 0)}%")
                d3.metric("总收益",   f"{dm.get('total_return', 0)}%")
                d4.metric("年化收益", f"{dm.get('annualized_return', 0)}%")
                d5.metric("最大回撤", f"{dm.get('max_drawdown', 0)}%")
                d6.metric("Sharpe",   dm.get("sharpe_ratio", 0))

                dt_trades = detail.get("trades", [])
                if dt_trades:
                    _exit_cn = {"STOP_LOSS": "止损", "TARGET": "止盈",
                                "SIGNAL": "信号平仓", "END_OF_DATA": "数据结束"}
                    dt_df = pd.DataFrame(dt_trades).rename(columns={
                        "signal_type": "信号", "open_date": "买入日",
                        "close_date": "卖出日", "entry_price": "买入价",
                        "exit_price": "卖出价", "pnl_pct": "盈亏%",
                        "exit_reason": "退出原因", "hold_days": "持仓天",
                    })
                    if "信号" in dt_df.columns:
                        dt_df["信号"] = dt_df["信号"].map(
                            lambda x: f"{CN.signal(x)} ({x})"
                        )
                    if "退出原因" in dt_df.columns:
                        dt_df["退出原因"] = dt_df["退出原因"].map(
                            lambda r: _exit_cn.get(r, r)
                        )
                    for drop_c in ["stock_code", "shares", "pnl_amount", "stop_loss", "target"]:
                        if drop_c in dt_df.columns:
                            dt_df = dt_df.drop(columns=[drop_c])
                    st.dataframe(dt_df, use_container_width=True, hide_index=True)
