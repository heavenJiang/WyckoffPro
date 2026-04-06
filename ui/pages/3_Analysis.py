"""
ui/pages/3_Analysis.py
"""
import streamlit as st
import sys
import os
import json
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from main import storage, collector, daily_analysis_pipeline, channel_analyzer, pnf_analyzer
from ui.components.glossary import tip, md_tip
from ui.components.kline_chart import render_kline_chart
from ui.components.pnf_chart import render_pnf_chart
from ui.components.signal_panel import render_signal_panel
from ui.components.advice_card import render_advice_card
from ui.components.counter_evidence_bar import render_counter_evidence_bar
from ui.components.phase_bar import render_phase_bar
from ui.components.translations import CN
import asyncio

st.set_page_config(page_title="Deep Analysis - WyckoffPro", page_icon="🔬", layout="wide")

# ── 股票选择 ────────────────────────────────────────────────────────────
wl = storage.get_watchlist()
if not wl:
    st.warning("自选股为空")
    st.stop()

stock_list = [f"{w['stock_code']} - {w.get('stock_name', '')}" for w in wl]
sel_stock  = st.selectbox("选择分析标的", stock_list)
if not sel_stock:
    st.stop()

stock_code = sel_stock.split(" ")[0]

col_btn, col_plans, col_tf, col_start, col_end, _ = st.columns([1, 1, 1, 1, 1, 1])
with col_btn:
    force_run = st.button("🔄 刷新分析", type="primary")
with col_plans:
    st.page_link("pages/4_Plans.py", label="📋 交易计划", icon="📋")
with col_tf:
    tf_label = st.selectbox("周期", ["日线", "周线", "月线"],
                            key="analysis_tf", label_visibility="collapsed")
    TF_MAP = {"日线": "daily", "周线": "weekly", "月线": "monthly"}
    # 威科夫默认回溯：日线2年/周线5年/月线10年（孟洪涛《威科夫操盘法》）
    TF_DEFAULT_DAYS = {"日线": 365, "周线": 365 * 3, "月线": 365 * 7}
    analysis_tf = TF_MAP[tf_label]
with col_start:
    analysis_start = st.date_input(
        "开始日期",
        value=date.today() - timedelta(days=TF_DEFAULT_DAYS[tf_label]),
        key=f"analysis_start_{tf_label}", label_visibility="collapsed",
    )
with col_end:
    analysis_end = st.date_input(
        "结束日期", value=date.today(),
        key=f"analysis_end_{tf_label}", label_visibility="collapsed",
    )

# ── 刷新分析：运行 pipeline ─────────────────────────────────────────────
if force_run:
    # ── Step 1: 数据新鲜度检查 & 显式同步（UI 层，可见反馈）──
    STALE_THRESHOLDS = {"daily": 3, "weekly": 10, "monthly": 35}
    _stale_days = STALE_THRESHOLDS.get(analysis_tf, 3)
    _latest_raw = storage.get_latest_date(stock_code, analysis_tf)
    _latest_dt  = None
    _days_old   = 9999
    if _latest_raw:
        try:
            _latest_dt = pd.to_datetime(str(_latest_raw))
            _days_old  = (date.today() - _latest_dt.date()).days
        except Exception:
            pass

    _sync_placeholder = st.empty()
    if _days_old > _stale_days:
        _date_str = str(_latest_dt.date()) if _latest_dt else "未知"
        _sync_placeholder.info(f"📡 **{stock_code}** 数据截至 {_date_str}（距今 {_days_old} 天），正在同步最新数据…")
        _start_fetch = ((_latest_dt + timedelta(days=1)).strftime("%Y%m%d")
                        if _latest_dt else
                        (date.today() - timedelta(days=730)).strftime("%Y%m%d"))
        try:
            _df_new = collector.fetch_klines(stock_code, analysis_tf, _start_fetch)
            if not _df_new.empty:
                storage.save_klines(stock_code, _df_new, analysis_tf)
                _new_latest = _df_new["trade_date"].max()
                _sync_placeholder.success(
                    f"✅ 数据同步完成：新增 **{len(_df_new)}** 条，最新交易日 **{_new_latest}**"
                )
            else:
                _sync_placeholder.warning("⚠️ 数据源未返回新数据（可能是非交易日或数据源限流），继续使用已有数据分析")
        except Exception as _se:
            _sync_placeholder.error(f"❌ 数据同步失败：{_se}")
    else:
        _sync_placeholder.success(
            f"✅ 数据已是最新（最新交易日 {_latest_dt.date() if _latest_dt else '—'}，距今 {_days_old} 天）"
        )

    # ── Step 2a: 纯规则分析（快速）──
    with st.spinner("📐 运行纯规则分析…"):
        try:
            res_rule = asyncio.run(daily_analysis_pipeline(stock_code, analysis_tf, ai_enabled=False))
            if "error" in res_rule:
                st.error(res_rule["error"]); st.stop()
            st.session_state[f"res_rule_{stock_code}"] = res_rule
        except Exception as e:
            st.error(f"规则分析异常: {e}"); st.stop()

    # ── Step 2b: AI 增强分析（较慢）──
    with st.spinner("🤖 运行 AI 证伪增强分析（需联网，请稍候）…"):
        try:
            res_ai = asyncio.run(daily_analysis_pipeline(stock_code, analysis_tf, ai_enabled=True))
            if "error" in res_ai:
                st.warning(f"AI分析异常，仅展示规则结果：{res_ai['error']}")
                res_ai = None
            else:
                st.session_state[f"res_ai_{stock_code}"] = res_ai
                st.session_state[f"exec_meta_{stock_code}"] = res_ai.get("execution_meta", {})
        except Exception as e:
            st.warning(f"AI分析异常，仅展示规则结果：{e}")
            res_ai = None

    st.success("分析完成。")

# ── 从 DB 加载最新数据 ──────────────────────────────────────────────────
df      = storage.get_klines(stock_code, analysis_tf,
                             start_date=analysis_start.strftime("%Y-%m-%d"))
if not df.empty:
    df = df[df["trade_date"] <= analysis_end.strftime("%Y-%m-%d")]
phase   = storage.get_current_phase(stock_code, analysis_tf)
ce_data = storage.get_counter_evidence(stock_code)
advice  = storage.get_latest_advice(stock_code) or {}

if phase:
    try:
        from engine.phase_fsm import PhaseState
        ps = PhaseState(stock_code=stock_code, **{
            k: v for k, v in phase.items()
            if k in ["phase_code", "confidence", "start_date",
                     "tr_upper", "tr_lower", "ice_line", "creek_line", "timeframe"]
        })
    except Exception:
        ps = None
else:
    ps = None

ce_score  = ce_data.get("current_score", 0) if ce_data else 0
ce_alert  = ce_data.get("alert_level", "NONE") if ce_data else "NONE"
ce_events = ce_data.get("events", []) if ce_data else []

with storage._get_conn() as _c:
    _chain = _c.execute(
        "SELECT completion_pct FROM signal_chain WHERE stock_code=? AND status='ACTIVE' ORDER BY id DESC LIMIT 1",
        (stock_code,)
    ).fetchone()
    chain_pct = _chain["completion_pct"] if _chain else 0

    _sigs = _c.execute(
        "SELECT * FROM wyckoff_signal WHERE stock_code=? AND timeframe=? ORDER BY signal_date DESC LIMIT 100",
        (stock_code, analysis_tf)
    ).fetchall()
    # 按 (signal_type, signal_date) 去重，保留 likelihood 最高的一条
    _seen: dict = {}
    for r in _sigs:
        key = (r["signal_type"], r["signal_date"])
        if key not in _seen or r["likelihood"] > _seen[key]["likelihood"]:
            _seen[key] = dict(r)
    signals = sorted(_seen.values(), key=lambda s: s["signal_date"], reverse=True)[:20]

execution_meta = st.session_state.get(f"exec_meta_{stock_code}", {})

# ── Tab 布局 ────────────────────────────────────────────────────────────
tab_current, tab_history = st.tabs(["🔬 当前分析", "🕰️ 历史版本"])

# ════════════════════════════════════════════════════════════════════════
# Tab 1: 当前分析
# ════════════════════════════════════════════════════════════════════════
with tab_current:
    if df.empty:
        st.warning("数据加载失败，请检查数据库或点击「刷新分析」重新获取数据。")
    else:
        st.title(f"🔬 {sel_stock} 深度技术分析")
        _last_date = df["trade_date"].iloc[-1] if not df.empty else ""
        _today = date.today()
        try:
            _days_old = (_today - pd.to_datetime(str(_last_date)).date()).days
        except Exception:
            _days_old = 0
        if _days_old > 5:
            st.warning(f"⚠️ 数据最新至 **{_last_date}**，距今 {_days_old} 天，建议点击「刷新分析」补全最新数据。")
        elif _days_old > 2:
            st.info(f"📅 数据最新至 **{_last_date}**（{_days_old} 天前），如需最新结果请点击「刷新分析」。")
        st.caption(f"周期：{tf_label} ｜ 数据范围：{analysis_start} ~ {analysis_end} ｜ 共 {len(df)} 根K线 ｜ 最新交易日：{_last_date}")

        # ── 公共数据 ──────────────────────────────────────────────────────
        phase_code = getattr(ps, "phase_code", "UNKNOWN") if ps else "UNKNOWN"
        phase_conf = getattr(ps, "confidence", 0) if ps else 0

        # ── 区域 A：双轨分析对比卡（图表之上，全宽）────────────────────
        res_rule_data = st.session_state.get(f"res_rule_{stock_code}")
        res_ai_data   = st.session_state.get(f"res_ai_{stock_code}")

        # 若 session 无数据，从 DB 最新快照重建（默认展示）
        if not res_rule_data and not res_ai_data:
            def _snap_to_res(snap: dict) -> dict:
                return {
                    "phase":            snap.get("phase_code"),
                    "phase_confidence": snap.get("phase_confidence", 0),
                    "advice": {
                        "advice_type": snap.get("advice_type", "WAIT"),
                        "confidence":  snap.get("confidence", 0),
                    },
                    "quant_total":        snap.get("quant_total", 0),
                    "nine_tests_passed":  snap.get("nine_tests_passed", 0),
                    "counter_score":      snap.get("counter_score", 0),
                    "alert_level":        snap.get("alert_level", "NONE"),
                    "falsification_summary": None,  # 快照未存完整证伪细节
                }
            _snaps_r = storage.get_analysis_snapshots(stock_code, limit=1, ai_enabled=0)
            _snaps_a = storage.get_analysis_snapshots(stock_code, limit=1, ai_enabled=1)
            if _snaps_r:
                res_rule_data = _snap_to_res(_snaps_r[0])
            if _snaps_a:
                res_ai_data = _snap_to_res(_snaps_a[0])

        if res_rule_data or res_ai_data:
            # ── 提取数据工具 ──────────────────────────────────────────
            def _get(src, *keys, default=None, cast=None):
                v = src or {}
                for k in keys:
                    v = v.get(k) if isinstance(v, dict) else None
                    if v is None:
                        return default
                return cast(v) if cast and v is not None else v

            r_type  = _get(res_rule_data, "advice", "advice_type", default="WAIT")
            r_conf  = _get(res_rule_data, "advice", "confidence",  default=0,    cast=float)
            r_phase = _get(res_rule_data, "phase",                 default="UNKNOWN")
            r_pconf = _get(res_rule_data, "phase_confidence",      default=0,    cast=float)
            r_qt    = _get(res_rule_data, "quant_total",           default=0,    cast=float)
            r_nine  = _get(res_rule_data, "nine_tests_passed",     default=0,    cast=int)
            r_ce    = _get(res_rule_data, "counter_score",         default=0,    cast=float)
            r_alert = _get(res_rule_data, "alert_level",           default="NONE")

            a_type  = _get(res_ai_data, "advice", "advice_type", default=None)
            a_conf  = _get(res_ai_data, "advice", "confidence",  default=None, cast=float)
            a_phase = _get(res_ai_data, "phase",                 default=None)
            a_pconf = _get(res_ai_data, "phase_confidence",      default=None, cast=float)
            a_qt    = _get(res_ai_data, "quant_total",           default=None, cast=float)
            a_nine  = _get(res_ai_data, "nine_tests_passed",     default=None, cast=int)
            a_ce    = _get(res_ai_data, "counter_score",         default=None, cast=float)
            a_alert = _get(res_ai_data, "alert_level",           default=None)

            advice_changed = bool(a_type and a_type != r_type)

            # AI建议变化提示
            if advice_changed:
                st.warning(
                    f"⚡ AI建议与规则建议不同：规则 **{CN.advice(r_type)}** → AI **{CN.advice(a_type)}**"
                )

            # ── 双栏对比卡（纯 HTML table，紧凑对比）──────────────────
            card_r, card_a = st.columns(2)

            def _dhtml(new, base, unit="", invert=False):
                """带颜色的 delta 片段，差值 < 0.5 时不显示"""
                if new is None or base is None or abs(new - base) < 0.5:
                    return ""
                d = new - base
                up = (d > 0) != invert
                clr = "#4ade80" if up else "#f87171"
                return f'<span style="color:{clr};font-size:10px;"> ({"+" if d>0 else ""}{d:.0f}{unit})</span>'

            TD_L = 'style="color:#6b7280;padding:3px 6px 3px 0;white-space:nowrap;"'
            TD_R = 'style="color:#e5e7eb;text-align:right;padding:3px 0;"'

            # 纯规则卡
            with card_r:
                with st.container(border=True):
                    r_alert_cn, r_alert_clr = CN.alert(r_alert)
                    st.markdown(
                        "**📐 纯规则**&emsp;" + CN.advice_badge(r_type, "12px"),
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"""
<table style="width:100%;border-collapse:collapse;font-size:12px;margin-top:4px;">
  <tr><td {TD_L}>威科夫阶段</td>
      <td {TD_R}><b>{CN.phase(r_phase)}</b> <span style="color:#6b7280;font-size:10px;">({r_phase})</span></td></tr>
  <tr><td {TD_L}>阶段置信度</td>
      <td {TD_R}>{r_pconf:.0f}%</td></tr>
  <tr><td {TD_L}>操作置信度</td>
      <td {TD_R}>{r_conf:.0f}%</td></tr>
  <tr><td {TD_L}>量化评分</td>
      <td {TD_R}>{r_qt:.0f}/100</td></tr>
  <tr><td {TD_L}>九大测试</td>
      <td {TD_R}>{r_nine}/9</td></tr>
  <tr><td {TD_L}>反面积分</td>
      <td style="color:{r_alert_clr};font-weight:600;text-align:right;padding:3px 0;">{r_ce:.0f}&nbsp;{r_alert_cn}</td></tr>
</table>
""", unsafe_allow_html=True)

            # AI增强卡
            with card_a:
                with st.container(border=True):
                    if res_ai_data:
                        a_alert_cn, a_alert_clr = CN.alert(a_alert)
                        st.markdown(
                            "**🤖 AI增强**&emsp;" + CN.advice_badge(a_type or "WAIT", "12px"),
                            unsafe_allow_html=True,
                        )
                        st.markdown(f"""
<table style="width:100%;border-collapse:collapse;font-size:12px;margin-top:4px;">
  <tr><td {TD_L}>威科夫阶段</td>
      <td {TD_R}><b>{CN.phase(a_phase or "UNKNOWN")}</b> <span style="color:#6b7280;font-size:10px;">({a_phase})</span></td></tr>
  <tr><td {TD_L}>阶段置信度</td>
      <td {TD_R}>{a_pconf:.0f}%{_dhtml(a_pconf, r_pconf, "%")}</td></tr>
  <tr><td {TD_L}>操作置信度</td>
      <td {TD_R}>{a_conf:.0f}%{_dhtml(a_conf, r_conf, "%")}</td></tr>
  <tr><td {TD_L}>量化评分</td>
      <td {TD_R}>{a_qt:.0f}/100{_dhtml(a_qt, r_qt)}</td></tr>
  <tr><td {TD_L}>九大测试</td>
      <td {TD_R}>{a_nine}/9</td></tr>
  <tr><td {TD_L}>反面积分</td>
      <td style="color:{a_alert_clr};font-weight:600;text-align:right;padding:3px 0;">{a_ce:.0f}&nbsp;{a_alert_cn}{_dhtml(a_ce, r_ce, invert=True)}</td></tr>
</table>
""", unsafe_allow_html=True)
                        # AI证伪详情
                        falsi = res_ai_data.get("falsification_summary")
                        if falsi:
                            with st.expander("🔬 AI证伪详情", expanded=True):
                                gate_cn, gate_clr = CN.gate(falsi.get("gate", "PASS"))
                                st.caption(
                                    f"{gate_cn}  ·  "
                                    f"置信度调整 {falsi.get('conf_delta', 0):+.0f}  ·  "
                                    f"反面积分调整 {falsi.get('ce_delta', 0):+.0f}"
                                )
                                sig_res = falsi.get("signal_results") or {}
                                if sig_res:
                                    parts = []
                                    for k, v in sig_res.items():
                                        vd = CN.verdict(v)
                                        parts.append(f"{vd.split()[0]} **{CN.signal(k)}**({k})")
                                    st.markdown("信号：" + "  ".join(parts))
                                if falsi.get("phase_result"):
                                    st.markdown(f"阶段：{CN.verdict(falsi['phase_result'])}")
                                if falsi.get("narrative"):
                                    st.markdown(f"叙事：{CN.narrative(falsi['narrative'])}")
                    else:
                        st.markdown("**🤖 AI增强分析**")
                        st.caption("AI分析未运行，仅显示规则结果。")

        else:
            # 真正首次加载且无任何历史快照
            st.info("暂无分析数据，请点击「刷新分析」运行首次分析。")

        # ── 区域 B：状态指标横排（阶段 / 反面积分 / 信号链）────────────
        pb_col, ce_col, chain_col = st.columns([5, 5, 2])
        with pb_col:
            render_phase_bar(phase_code, phase_conf)
        with ce_col:
            render_counter_evidence_bar(ce_score, ce_alert, ce_events)
        with chain_col:
            st.metric("信号链完成度", f"{chain_pct}%", help=tip("信号链完成度"))

        # ── 区域 C：K线图 + P&F（全宽）──────────────────────────────
        st.divider()
        channel = channel_analyzer.analyze(
            df,
            getattr(ps, "tr_upper", 0) if ps else 0,
            getattr(ps, "tr_lower", 0) if ps else 0,
        )
        render_kline_chart(df, signals=signals, phase_state=ps, channel=channel, height=650)

        st.markdown("**" + md_tip("点数图") + "**", unsafe_allow_html=True)
        pnf = pnf_analyzer.build(df)
        render_pnf_chart(pnf)

        # ── 区域 D：信号面板 + 执行元数据（折叠）────────────────────
        if signals:
            with st.expander(f"📡 信号明细（共 {len(signals)} 条）", expanded=False):
                render_signal_panel(signals)

        if execution_meta:
            with st.expander("🚀 本次分析执行元数据", expanded=False):
                st.info(
                    f"分析流在 **{execution_meta.get('start_time', '—')}** 启动，"
                    f"总执行耗时: **{execution_meta.get('total_duration', '—')}s**"
                )
                steps = execution_meta.get("steps", [])
                if steps:
                    st.dataframe(pd.DataFrame(steps), use_container_width=True, hide_index=True)
        else:
            st.caption("点击「刷新分析」后此处将显示本次执行性能指标。")


# ════════════════════════════════════════════════════════════════════════
# Tab 2: 历史版本
# ════════════════════════════════════════════════════════════════════════
with tab_history:
    _mode_filter = st.radio(
        "显示模式", ["全部", "📐 仅规则", "🤖 仅AI"],
        horizontal=True, key="hist_mode_filter",
        label_visibility="collapsed",
    )
    _ai_param = None if _mode_filter == "全部" else (0 if "规则" in _mode_filter else 1)
    snapshots = storage.get_analysis_snapshots(stock_code, limit=60, ai_enabled=_ai_param)

    if not snapshots:
        st.info("暂无历史分析记录。点击「刷新分析」后将开始积累历史版本。")
    else:
        st.caption(f"共 **{len(snapshots)}** 条历史分析记录（最近60条）")

        # ── 趋势图 ─────────────────────────────────────────────────────
        df_snap = pd.DataFrame(snapshots)
        df_snap["run_at_dt"] = pd.to_datetime(df_snap["run_at"])
        df_snap = df_snap.sort_values("run_at_dt")

        # ── 趋势图：置信度/反面积分 + 量化总分（2行，左右各一列）──
        ch_left, ch_right = st.columns(2)

        with ch_left:
            st.caption("📈 置信度 & 反面积分走势")
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(
                x=df_snap["run_at_dt"], y=df_snap["confidence"],
                name="置信度%", line=dict(color="#42a5f5", width=2),
                fill="tozeroy", fillcolor="rgba(66,165,245,0.08)",
            ))
            fig1.add_trace(go.Scatter(
                x=df_snap["run_at_dt"], y=df_snap["counter_score"],
                name="反面积分", line=dict(color="#ef5350", width=2),
                fill="tozeroy", fillcolor="rgba(239,83,80,0.08)",
            ))
            fig1.add_hline(y=31, line_dash="dot", line_color="#fbbf24",
                           annotation_text="黄线31", annotation_position="bottom right")
            fig1.add_hline(y=71, line_dash="dot", line_color="#ef4444",
                           annotation_text="红线71", annotation_position="bottom right")
            fig1.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=8, b=0),
                plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                font=dict(color="#fafafa", size=11),
                legend=dict(orientation="h", y=1.04, x=0),
                yaxis=dict(range=[0, 105], gridcolor="#1e2533"),
                xaxis=dict(gridcolor="#1e2533"),
            )
            st.plotly_chart(fig1, use_container_width=True)

        with ch_right:
            st.caption("📊 量化总分（按建议分色）")
            _colors = df_snap["advice_type"].map({
                "STRONG_BUY": "#00c853", "BUY": "#69f0ae",
                "WATCH": "#ffeb3b", "HOLD": "#90a4ae",
                "WAIT": "#78909c", "REDUCE": "#ff7043",
                "SELL": "#f44336", "STRONG_SELL": "#b71c1c",
            }).fillna("#78909c")
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=df_snap["run_at_dt"], y=df_snap["quant_total"],
                name="量化总分",
                marker_color=_colors,
                text=df_snap["advice_type"].map(CN.ADVICE).fillna(""),
                textposition="outside",
                textfont=dict(size=9),
            ))
            fig2.add_hline(y=65, line_dash="dot", line_color="#fbbf24",
                           annotation_text="关注线65", annotation_position="bottom right")
            fig2.add_hline(y=80, line_dash="dot", line_color="#00c853",
                           annotation_text="强信号80", annotation_position="bottom right")
            fig2.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=8, b=0),
                plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
                font=dict(color="#fafafa", size=11),
                showlegend=False,
                yaxis=dict(range=[0, 110], gridcolor="#1e2533"),
                xaxis=dict(gridcolor="#1e2533"),
            )
            st.plotly_chart(fig2, use_container_width=True)

        # ── 动态走势解读 ──
        _last   = df_snap.iloc[-1]
        _first  = df_snap.iloc[0]
        _conf   = float(_last.get("confidence") or 0)
        _ce     = float(_last.get("counter_score") or 0)
        _qt     = float(_last.get("quant_total") or 0)
        _conf0  = float(_first.get("confidence") or 0)
        _ce0    = float(_first.get("counter_score") or 0)

        # 置信度趋势
        if _conf > _conf0 + 5:
            conf_txt = f"置信度 {_conf:.0f}%，较首条记录上升 {_conf-_conf0:.0f}%，阶段判断趋于清晰"
            conf_clr = "#42a5f5"
        elif _conf < _conf0 - 5:
            conf_txt = f"置信度 {_conf:.0f}%，较首条记录下降 {_conf0-_conf:.0f}%，市场结构趋于模糊"
            conf_clr = "#f39c12"
        else:
            conf_txt = f"置信度 {_conf:.0f}%，较稳定"
            conf_clr = "#9ca3af"

        # 反面积分评估
        if _ce >= 71:
            ce_txt = f"反面积分 {_ce:.0f} — 🚨 红色警戒，已触发紧急反转审查，不宜做多"
            ce_clr = "#ef5350"
        elif _ce >= 51:
            ce_txt = f"反面积分 {_ce:.0f} — ⚠️ 橙色预警，BUY 建议自动降为 WATCH"
            ce_clr = "#ff7043"
        elif _ce >= 31:
            ce_txt = f"反面积分 {_ce:.0f} — 🟡 黄色关注，存在一定反面证据，需持续观察"
            ce_clr = "#ffd600"
        else:
            ce_txt = f"反面积分 {_ce:.0f} — 绿色健康，无显著反面证据"
            ce_clr = "#2ecc71"

        # 矛盾信号检测
        diverge_txt = ""
        if _conf > _conf0 and _ce > _ce0 + 10:
            diverge_txt = "⚡ 注意：置信度上升但反面积分也在升高，市场存在矛盾信号，需谨慎对待当前建议。"

        # 量化总分评价
        if _qt >= 80:
            qt_txt = f"量化总分 {_qt:.0f}/100，较高，五维评估整体偏强"
            qt_clr = "#2ecc71"
        elif _qt >= 65:
            qt_txt = f"量化总分 {_qt:.0f}/100，中等偏上，具备关注价值"
            qt_clr = "#f39c12"
        else:
            qt_txt = f"量化总分 {_qt:.0f}/100，偏低，条件尚不成熟"
            qt_clr = "#ef5350"

        _rows = [
            f'<span style="color:{conf_clr}">▪ <b>置信度</b>　{conf_txt}</span>',
            f'<span style="color:{ce_clr}">▪ <b>反面积分</b>　{ce_txt}</span>',
            f'<span style="color:{qt_clr}">▪ <b>量化总分</b>　{qt_txt}（大盘共振/30 + 阶段/25 + 信号链/20 + MTF/15 + 供需/10）</span>',
        ]
        if diverge_txt:
            _rows.append(f'<span style="color:#ff7043">▪ {diverge_txt}</span>')
        st.markdown(f"""
<div style="background:#111827; border-left:3px solid #374151; padding:10px 14px;
            border-radius:0 4px 4px 0; font-size:12px; color:#9ca3af; margin-top:-8px;">
{"<br>".join(_rows)}
</div>
""", unsafe_allow_html=True)

        # ── 阶段变化时间线 ──────────────────────────────────────────────
        with st.expander("阶段演变时间线", expanded=False):
            phase_seq = df_snap[["run_at", "phase_code", "phase_confidence"]].copy()
            phase_seq["run_at"] = phase_seq["run_at"].str[:16]
            phase_seq["phase_code"] = phase_seq["phase_code"].map(
                lambda c: f"{CN.phase(c)} ({c})"
            )
            st.dataframe(phase_seq.rename(columns={
                "run_at": "时间", "phase_code": "阶段", "phase_confidence": "置信度%"
            }), use_container_width=True, hide_index=True)

        # ── 历史版本列表 ────────────────────────────────────────────────
        st.subheader("版本明细")

        table_rows = []
        for s in snapshots:
            sig_list = s.get("signals_json") or []
            if isinstance(sig_list, list):
                sig_str = " ".join(
                    f"{CN.signal(x.get('signal_type','?'))}({x.get('likelihood',0):.0%})"
                    for x in sig_list[:5]
                )
            else:
                sig_str = "—"
            _ai_flag = s.get("ai_enabled", 1)
            _atype   = s.get("advice_type", "")
            _alert   = s.get("alert_level", "")
            _gate_cn, _ = CN.gate(_alert)
            table_rows.append({
                "模式":      "🤖 AI" if _ai_flag else "📐 规则",
                "时间":      str(s["run_at"])[:16],
                "K线日期":   s.get("trade_date", "—"),
                "阶段":      CN.phase(s.get("phase_code", "UNKNOWN")),
                "建议":      f"{CN.advice_icon(_atype)} {CN.advice(_atype)}",
                "置信度":    s.get("confidence", 0),
                "量化分":    s.get("quant_total", 0),
                "反面积分":  s.get("counter_score", 0),
                "门控":      _gate_cn,
                "九测通过":  s.get("nine_tests_passed", 0),
                "链完成%":   s.get("chain_completion", 0),
                "信号":      sig_str,
                "耗时(s)":   s.get("total_duration"),
            })

        df_table = pd.DataFrame(table_rows)
        st.dataframe(
            df_table,
            use_container_width=True,
            hide_index=True,
            height=400,
            column_config={
                "置信度":   st.column_config.ProgressColumn("置信度", min_value=0, max_value=100, format="%.0f%%"),
                "量化分":   st.column_config.NumberColumn("量化分", format="%.1f"),
                "反面积分": st.column_config.NumberColumn("反面积分", help=tip("反面积分")),
                "九测通过": st.column_config.NumberColumn("九测通过", help=tip("信号链完成度")),
                "链完成%":  st.column_config.ProgressColumn("链完成%", min_value=0, max_value=100, format="%.0f%%"),
                "耗时(s)":  st.column_config.NumberColumn("耗时(s)", format="%.2f"),
            },
        )

        # ── 单条版本详情 ────────────────────────────────────────────────
        st.divider()
        st.subheader("版本详情")
        snap_options = {
            s["id"]: (
                f"#{s['id']} | {str(s['run_at'])[:16]} | "
                f"{CN.phase(s.get('phase_code','UNKNOWN'))} | "
                f"{CN.advice_icon(s.get('advice_type',''))} {CN.advice(s.get('advice_type',''))} "
                f"{s.get('confidence',0):.0f}%"
            )
            for s in snapshots
        }
        sel_snap_id = st.selectbox(
            "选择版本",
            options=list(snap_options.keys()),
            format_func=lambda x: snap_options[x],
        )
        if sel_snap_id:
            snap = next(s for s in snapshots if s["id"] == sel_snap_id)
            _snap_ai = snap.get("ai_enabled", 1)
            st.caption(f"分析模式: {'🤖 AI增强' if _snap_ai else '📐 纯规则'}")

            _spc = snap.get("phase_code", "UNKNOWN")
            _sat = snap.get("advice_type", "WAIT")
            d1, d2, d3, d4, d5 = st.columns(5)
            d1.metric("阶段",    CN.phase(_spc), help=_spc)
            d2.metric("建议",    f"{CN.advice_icon(_sat)} {CN.advice(_sat)}")
            d3.metric("置信度",  f"{snap.get('confidence', 0):.0f}%")
            d4.metric("反面积分", snap.get("counter_score", 0), help=tip("反面积分"))
            d5.metric("门控",    CN.gate(snap.get("falsification_gate", "PASS"))[0])

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**本次检测到的信号**")
                sig_list = snap.get("signals_json") or []
                if sig_list:
                    sig_df = pd.DataFrame(sig_list)
                    show_cols = [c for c in ["signal_type", "likelihood", "strength", "signal_date"] if c in sig_df.columns]
                    sig_df = sig_df[show_cols].copy()
                    if "signal_type" in sig_df.columns:
                        sig_df["signal_type"] = sig_df["signal_type"].map(
                            lambda x: f"{CN.signal(x)} ({x})"
                        )
                    sig_df = sig_df.rename(columns={
                        "signal_type": "信号类型", "likelihood": "似然度",
                        "strength": "强度", "signal_date": "日期",
                    })
                    st.dataframe(sig_df, use_container_width=True, hide_index=True)
                else:
                    st.caption("本次未检测到信号")

            with col_b:
                st.markdown("**执行步骤详情**")
                steps = snap.get("steps_json") or []
                if steps:
                    st.dataframe(pd.DataFrame(steps), use_container_width=True, hide_index=True)
                else:
                    st.caption("无执行步骤记录")
