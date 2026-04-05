"""
ui/pages/7_DataHub.py — Tushare Hub 数据仓库查看器
"""
import streamlit as st
import sys
import os
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from main import config

st.set_page_config(page_title="DataHub - WyckoffPro", page_icon="🗄️", layout="wide")
st.title("🗄️ 数据仓库 DataHub")

DB_PATH = config["data"].get("db_path", "data/wyckoffpro.db")


# ─── 工具函数 ──────────────────────────────────────────────
@st.cache_resource
def get_db():
    return DB_PATH

def query(sql: str, params=()) -> pd.DataFrame:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            return pd.read_sql(sql, conn, params=params)
    except Exception as e:
        return pd.DataFrame()

def table_stats() -> pd.DataFrame:
    """查询所有扩展表的行数和最近更新时间"""
    tables = [
        ("stock_basic",         "A股列表",     "基础数据"),
        ("etf_basic",           "ETF列表",      "基础数据"),
        ("option_basic",        "期权列表",     "基础数据"),
        ("st_stocks",           "ST股票",       "基础数据"),
        ("hs_const",            "沪深港通",     "基础数据"),
        ("financial_income",    "利润表",       "财务数据"),
        ("financial_balance",   "资产负债表",   "财务数据"),
        ("financial_cashflow",  "现金流量表",   "财务数据"),
        ("financial_indicator", "财务指标",     "财务数据"),
        ("forecast",            "业绩预告",     "财务数据"),
        ("dividend",            "分红送股",     "财务数据"),
        ("macro_gdp",           "GDP",          "宏观经济"),
        ("macro_cpi",           "CPI",          "宏观经济"),
        ("macro_money",         "货币供应",     "宏观经济"),
        ("pledge_stat",         "质押统计",     "参考数据"),
        ("share_float",         "限售解禁",     "参考数据"),
        ("repurchase",          "回购",         "参考数据"),
        ("holder_trade",        "增减持",       "参考数据"),
        ("top_list",            "龙虎榜",       "参考数据"),
        ("margin",              "融资融券",     "参考数据"),
        ("concept",             "概念板块",     "特色数据"),
        ("concept_detail",      "概念成分",     "特色数据"),
        ("moneyflow",           "资金流向",     "特色数据"),
        ("broker_recommend",    "券商金股",     "特色数据"),
        ("cyq_perf",            "筹码分布",     "特色数据"),
        ("stk_factor",          "量化因子",     "特色数据"),
        ("report_rc",           "盈利预测",     "特色数据"),
        ("stk_surv",            "机构调研",     "特色数据"),
        ("stk_auction",         "集合竞价",     "特色数据"),
    ]
    rows = []
    with sqlite3.connect(DB_PATH) as conn:
        for tbl, label, category in tables:
            try:
                cnt = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                upd = conn.execute(
                    f"SELECT MAX(updated_at) FROM {tbl}"
                ).fetchone()[0] or "—"
                if upd and len(upd) > 10:
                    upd = upd[:10]
            except Exception:
                cnt, upd = 0, "—"
            rows.append({
                "分类": category, "表名": tbl, "说明": label,
                "记录数": cnt, "最近更新": upd,
            })
    return pd.DataFrame(rows)


# ─── 顶部：总览指标 ────────────────────────────────────────
stats = table_stats()
total_rows = stats["记录数"].sum()
synced_tables = (stats["记录数"] > 0).sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("已同步表数", f"{synced_tables} / {len(stats)}")
c2.metric("总记录数", f"{total_rows:,}")
c3.metric("A股总数", f"{query('SELECT COUNT(*) as n FROM stock_basic').iloc[0]['n']:,}" if synced_tables else "0")
c4.metric("概念板块", f"{query('SELECT COUNT(*) as n FROM concept').iloc[0]['n']:,}" if synced_tables else "0")

st.divider()

# ─── 主 Tab 导航 ───────────────────────────────────────────
tab_overview, tab_basic, tab_mkt, tab_fin, tab_macro, tab_ref, tab_special = st.tabs([
    "📋 总览", "🏢 基础数据", "📈 行情因子", "💰 财务数据",
    "🌐 宏观经济", "📌 参考数据", "✨ 特色数据",
])


# ══════════════════════════════════════════════════════════
# Tab 1: 总览
# ══════════════════════════════════════════════════════════
with tab_overview:
    st.subheader("数据仓库状态总览")

    # 分类图标映射（替代背景着色）
    CATEGORY_ICON = {
        "基础数据": "🏢",
        "财务数据": "💰",
        "宏观经济": "🌐",
        "参考数据": "📌",
        "特色数据": "✨",
    }
    STATUS_ICON = lambda n: "✅" if n > 0 else "⭕"

    display = stats.copy()
    display.insert(0, "类别", display["分类"].map(CATEGORY_ICON) + " " + display["分类"])
    display["状态"] = display["记录数"].apply(STATUS_ICON)
    display["记录数"] = display["记录数"].apply(lambda x: f"{x:,}")
    display = display[["类别", "说明", "表名", "记录数", "最近更新", "状态"]]

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        height=700,
        column_config={
            "类别":     st.column_config.TextColumn(width="medium"),
            "说明":     st.column_config.TextColumn(width="small"),
            "表名":     st.column_config.TextColumn(width="medium"),
            "记录数":   st.column_config.TextColumn(width="small"),
            "最近更新": st.column_config.TextColumn(width="small"),
            "状态":     st.column_config.TextColumn(width="small"),
        },
    )

    st.divider()
    st.subheader("🔄 触发同步")
    st.caption("同步任务在后台运行，请查看终端日志确认进度。")
    col_a, col_b, col_c, col_d = st.columns(4)
    if col_a.button("📥 全量同步 hub-full", use_container_width=True):
        os.system("nohup python main.py hub-full > logs/hub_full.log 2>&1 &")
        st.success("全量同步已启动，日志写入 logs/hub_full.log")
    if col_b.button("📅 日度同步 hub-daily", use_container_width=True):
        os.system("nohup python main.py hub-daily > logs/hub_daily.log 2>&1 &")
        st.success("日度同步已启动")
    if col_c.button("📆 周度同步 hub-weekly", use_container_width=True):
        os.system("nohup python main.py hub-weekly > logs/hub_weekly.log 2>&1 &")
        st.success("周度同步已启动")
    if col_d.button("🗓️ 月度同步 hub-monthly", use_container_width=True):
        os.system("nohup python main.py hub-monthly > logs/hub_monthly.log 2>&1 &")
        st.success("月度同步已启动")


# ══════════════════════════════════════════════════════════
# Tab 2: 基础数据
# ══════════════════════════════════════════════════════════
with tab_basic:
    sub1, sub2, sub3, sub4 = st.tabs(["A股列表", "ETF", "ST股票", "沪深港通"])

    with sub1:
        st.subheader("A股基础信息查询")
        col1, col2, col3 = st.columns(3)
        kw      = col1.text_input("代码/名称关键字", placeholder="如 000001 或 平安")
        market  = col2.selectbox("市场", ["全部", "主板", "创业板", "科创板", "北交所"])
        hs_flag = col3.selectbox("沪深港通", ["全部", "H（沪港通）", "S（深港通）", "N（未纳入）"])

        where, params = ["1=1"], []
        if kw:
            where.append("(ts_code LIKE ? OR name LIKE ?)")
            params += [f"%{kw}%", f"%{kw}%"]
        if market != "全部":
            mkt_map = {"主板": "主板", "创业板": "创业板", "科创板": "科创板", "北交所": "北交所"}
            where.append("market=?")
            params.append(mkt_map[market])
        if hs_flag != "全部":
            where.append("is_hs=?")
            params.append(hs_flag[0])

        sql = f"SELECT ts_code,name,area,industry,market,is_hs,list_date FROM stock_basic WHERE {' AND '.join(where)} ORDER BY ts_code LIMIT 500"
        df = query(sql, params)
        st.caption(f"共 {len(df)} 条（最多显示500）")
        st.dataframe(df, use_container_width=True, hide_index=True)

    with sub2:
        st.subheader("ETF 列表")
        df_etf = query("SELECT ts_code,name,fund_type,found_date,market FROM etf_basic ORDER BY ts_code")
        kw_etf = st.text_input("搜索ETF", placeholder="关键字")
        if kw_etf:
            df_etf = df_etf[df_etf["name"].str.contains(kw_etf, na=False) | df_etf["ts_code"].str.contains(kw_etf, na=False)]
        st.dataframe(df_etf, use_container_width=True, hide_index=True)

    with sub3:
        st.subheader("当前ST/退市风险股票")
        df_st = query("SELECT ts_code,name,start_date,end_date FROM st_stocks ORDER BY start_date DESC LIMIT 200")
        st.dataframe(df_st, use_container_width=True, hide_index=True)

    with sub4:
        st.subheader("沪深港通成分股")
        hs_type = st.radio("类型", ["SH（沪港通）", "SZ（深港通）"], horizontal=True)
        hs_code = hs_type[:2]
        df_hs = query("SELECT h.ts_code, s.name, h.in_date, h.out_date, h.is_new FROM hs_const h LEFT JOIN stock_basic s ON h.ts_code=s.ts_code WHERE h.hs_type=? ORDER BY h.ts_code", (hs_code,))
        st.dataframe(df_hs, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════
# Tab 3: 行情因子
# ══════════════════════════════════════════════════════════
with tab_mkt:
    st.subheader("行情因子查询")
    wl_df = query("SELECT ts_code, stock_name FROM watchlist")
    wl_options = [f"{r['ts_code']} {r['stock_name']}" for _, r in wl_df.iterrows()] if not wl_df.empty else []

    col1, col2, col3 = st.columns([2, 1, 1])
    selected = col1.selectbox("选择股票", wl_options) if wl_options else col1.text_input("输入代码", placeholder="如 300027.SZ")
    ts_code = selected.split()[0] if selected and " " in selected else selected

    end_dt   = datetime.now()
    start_dt = end_dt - timedelta(days=90)
    date_start = col2.date_input("开始日期", value=start_dt)
    date_end   = col3.date_input("结束日期", value=end_dt)
    start_str = date_start.strftime("%Y%m%d")
    end_str   = date_end.strftime("%Y%m%d")

    mkt_sub1, mkt_sub2 = st.tabs(["💸 资金流向", "📊 量化因子"])

    with mkt_sub1:
        df_mf = query(
            "SELECT trade_date, net_mf_amount, buy_elg_vol, sell_elg_vol, buy_lg_vol, sell_lg_vol FROM moneyflow WHERE ts_code=? AND trade_date BETWEEN ? AND ? ORDER BY trade_date",
            (ts_code, start_str, end_str)
        )
        if df_mf.empty:
            st.info("暂无资金流向数据")
        else:
            # 净流入趋势图
            st.caption(f"{ts_code} 近期资金流向（净流入万元）")
            st.bar_chart(df_mf.set_index("trade_date")["net_mf_amount"])
            with st.expander("查看明细数据"):
                st.dataframe(df_mf, use_container_width=True, hide_index=True)

    with mkt_sub2:
        df_sf = query(
            "SELECT trade_date, pe_ttm, pb, ps_ttm, volume_ratio, turnover_rate_f, total_mv, circ_mv FROM stk_factor WHERE ts_code=? AND trade_date BETWEEN ? AND ? ORDER BY trade_date",
            (ts_code, start_str, end_str)
        )
        if df_sf.empty:
            st.info("暂无量化因子数据")
        else:
            c1, c2 = st.columns(2)
            with c1:
                st.caption("PE(TTM) 趋势")
                st.line_chart(df_sf.set_index("trade_date")["pe_ttm"])
            with c2:
                st.caption("PB 趋势")
                st.line_chart(df_sf.set_index("trade_date")["pb"])
            with st.expander("查看全部因子明细"):
                st.dataframe(df_sf, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════
# Tab 4: 财务数据
# ══════════════════════════════════════════════════════════
with tab_fin:
    st.subheader("财务数据查询")
    wl_fin = query("SELECT ts_code, stock_name FROM watchlist")
    fin_options = [f"{r['ts_code']} {r['stock_name']}" for _, r in wl_fin.iterrows()] if not wl_fin.empty else []
    sel_fin = st.selectbox("选择股票", fin_options, key="fin_stock") if fin_options else st.text_input("输入代码", key="fin_code")
    ts_fin = sel_fin.split()[0] if sel_fin and " " in sel_fin else sel_fin

    fin_sub1, fin_sub2, fin_sub3, fin_sub4 = st.tabs(["核心指标", "利润表", "现金流", "业绩预告"])

    with fin_sub1:
        df_fi = query(
            "SELECT end_date, eps, bps, roe, roa, grossprofit_margin, netprofit_margin, debt_to_assets, current_ratio, pe, pb FROM financial_indicator WHERE ts_code=? ORDER BY end_date DESC LIMIT 12",
            (ts_fin,)
        )
        if df_fi.empty:
            st.info("暂无财务指标数据")
        else:
            # 最新一期卡片
            latest = df_fi.iloc[0]
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("ROE", f"{latest.get('roe', 0):.1f}%" if latest.get('roe') else "—")
            c2.metric("毛利率", f"{latest.get('grossprofit_margin', 0):.1f}%" if latest.get('grossprofit_margin') else "—")
            c3.metric("净利率", f"{latest.get('netprofit_margin', 0):.1f}%" if latest.get('netprofit_margin') else "—")
            c4.metric("资产负债率", f"{latest.get('debt_to_assets', 0):.1f}%" if latest.get('debt_to_assets') else "—")
            c5.metric("PE", f"{latest.get('pe', 0):.1f}x" if latest.get('pe') else "—")
            st.dataframe(df_fi, use_container_width=True, hide_index=True)

    with fin_sub2:
        df_inc = query(
            "SELECT end_date, report_type, revenue, n_income, operate_profit FROM financial_income WHERE ts_code=? ORDER BY end_date DESC LIMIT 12",
            (ts_fin,)
        )
        if df_inc.empty:
            st.info("暂无利润表数据")
        else:
            st.dataframe(df_inc, use_container_width=True, hide_index=True)
            st.caption("营收 vs 净利润（万元）")
            df_chart = df_inc[["end_date", "revenue", "n_income"]].dropna().set_index("end_date")
            st.bar_chart(df_chart)

    with fin_sub3:
        df_cf = query(
            "SELECT end_date, report_type, n_cashflow_act, n_cashflow_inv_act, n_cashflow_fnc_act, free_cashflow FROM financial_cashflow WHERE ts_code=? ORDER BY end_date DESC LIMIT 12",
            (ts_fin,)
        )
        if df_cf.empty:
            st.info("暂无现金流数据")
        else:
            st.dataframe(df_cf, use_container_width=True, hide_index=True)

    with fin_sub4:
        df_fc = query(
            "SELECT ann_date, end_date, type, p_change_min, p_change_max, summary FROM forecast WHERE ts_code=? ORDER BY ann_date DESC LIMIT 20",
            (ts_fin,)
        )
        if df_fc.empty:
            st.info("暂无业绩预告数据")
        else:
            for _, row in df_fc.iterrows():
                delta = f"{row['p_change_min']:.0f}% ~ {row['p_change_max']:.0f}%" if pd.notna(row.get('p_change_min')) else "—"
                color = "🟢" if str(row.get("type", "")).startswith("预增") or str(row.get("type", "")).startswith("扭亏") else "🔴"
                st.markdown(f"{color} **{row['ann_date']}** | 报告期 {row['end_date']} | 类型: **{row['type']}** | 净利润变幅: {delta}")
                if row.get("summary"):
                    st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;{row['summary'][:120]}")


# ══════════════════════════════════════════════════════════
# Tab 5: 宏观经济
# ══════════════════════════════════════════════════════════
with tab_macro:
    st.subheader("宏观经济指标")
    mc1, mc2, mc3 = st.columns(3)

    # GDP
    df_gdp = query("SELECT quarter, gdp, gdp_yoy FROM macro_gdp ORDER BY quarter DESC LIMIT 20")
    with mc1:
        if not df_gdp.empty:
            latest_gdp = df_gdp.iloc[0]
            st.metric("GDP 季度增速（最新）", f"{latest_gdp['gdp_yoy']:.1f}%", help=f"报告期 {latest_gdp['quarter']}")
        st.caption("GDP 同比增速 (%)")
        if not df_gdp.empty:
            st.line_chart(df_gdp.set_index("quarter")["gdp_yoy"].iloc[::-1])

    # CPI
    df_cpi = query("SELECT month, nt_val, nt_yoy FROM macro_cpi ORDER BY month DESC LIMIT 24")
    with mc2:
        if not df_cpi.empty:
            latest_cpi = df_cpi.iloc[0]
            st.metric("CPI 同比（最新）", f"{latest_cpi['nt_yoy']:.1f}%", help=f"报告期 {latest_cpi['month']}")
        st.caption("CPI 同比增速 (%)")
        if not df_cpi.empty:
            st.line_chart(df_cpi.set_index("month")["nt_yoy"].iloc[::-1])

    # M2
    df_m = query("SELECT month, m2, m2_yoy FROM macro_money ORDER BY month DESC LIMIT 24")
    with mc3:
        if not df_m.empty:
            latest_m = df_m.iloc[0]
            st.metric("M2 同比（最新）", f"{latest_m['m2_yoy']:.1f}%", help=f"报告期 {latest_m['month']}")
        st.caption("M2 同比增速 (%)")
        if not df_m.empty:
            st.line_chart(df_m.set_index("month")["m2_yoy"].iloc[::-1])

    st.divider()
    with st.expander("查看完整宏观数据表"):
        col_g, col_c, col_m = st.columns(3)
        with col_g:
            st.caption("GDP 历史")
            st.dataframe(df_gdp, hide_index=True, use_container_width=True)
        with col_c:
            st.caption("CPI 历史")
            st.dataframe(df_cpi, hide_index=True, use_container_width=True)
        with col_m:
            st.caption("货币供应量历史")
            st.dataframe(df_m, hide_index=True, use_container_width=True)


# ══════════════════════════════════════════════════════════
# Tab 6: 参考数据
# ══════════════════════════════════════════════════════════
with tab_ref:
    ref_sub1, ref_sub2, ref_sub3, ref_sub4, ref_sub5 = st.tabs([
        "⚠️ 质押风险", "🔓 近期解禁", "📈 增减持", "🐉 龙虎榜", "💳 融资融券"
    ])

    with ref_sub1:
        st.subheader("股权质押风险排行")
        df_pledge = query("""
            SELECT p.ts_code, s.name, p.end_date, p.pledge_count,
                   ROUND(p.pledge_ratio,2) as 质押比例_pct,
                   ROUND(p.total_shares/1e8,2) as 总股本_亿
            FROM pledge_stat p LEFT JOIN stock_basic s ON p.ts_code=s.ts_code
            ORDER BY p.pledge_ratio DESC LIMIT 100
        """)
        if not df_pledge.empty:
            high_risk = df_pledge[df_pledge["质押比例_pct"] >= 50]
            st.warning(f"质押比例 ≥ 50% 的股票：{len(high_risk)} 只") if not high_risk.empty else None
            pct_filter = st.slider("最低质押比例 (%)", 0, 100, 20)
            st.dataframe(df_pledge[df_pledge["质押比例_pct"] >= pct_filter], use_container_width=True, hide_index=True)
        else:
            st.info("暂无质押数据")

    with ref_sub2:
        st.subheader("近期限售股解禁")
        days_ahead = st.slider("未来天数", 7, 180, 60)
        today = datetime.now().strftime("%Y%m%d")
        future = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y%m%d")
        df_float = query("""
            SELECT f.ts_code, s.name, f.float_date, f.holder_name,
                   ROUND(f.float_share/1e8,2) as 解禁量_亿股,
                   ROUND(f.float_ratio,2) as 解禁比例_pct, f.share_type
            FROM share_float f LEFT JOIN stock_basic s ON f.ts_code=s.ts_code
            WHERE f.float_date BETWEEN ? AND ?
            ORDER BY f.float_date
        """, (today, future))
        if not df_float.empty:
            st.caption(f"未来 {days_ahead} 天内共 {len(df_float)} 笔解禁")
            st.dataframe(df_float, use_container_width=True, hide_index=True)
        else:
            st.info("该区间暂无解禁记录")

    with ref_sub3:
        st.subheader("股东增减持")
        col1, col2 = st.columns(2)
        direction = col1.selectbox("方向", ["全部", "IN 增持", "DE 减持"])
        holder_type = col2.selectbox("股东类型", ["全部", "G 高管", "P 大股东"])

        where_h, params_h = ["1=1"], []
        if direction != "全部":
            where_h.append("in_de=?")
            params_h.append(direction[:2])
        if holder_type != "全部":
            where_h.append("holder_type=?")
            params_h.append(holder_type[:1])

        df_ht = query(f"""
            SELECT h.ts_code, s.name, h.ann_date, h.holder_name, h.holder_type,
                   h.in_de, ROUND(h.change_vol/1e4,2) as 变动量_万股,
                   ROUND(h.change_ratio,2) as 变动比例_pct, ROUND(h.avg_price,2) as 均价
            FROM holder_trade h LEFT JOIN stock_basic s ON h.ts_code=s.ts_code
            WHERE {' AND '.join(where_h)}
            ORDER BY h.ann_date DESC LIMIT 200
        """, params_h)
        st.caption(f"共 {len(df_ht)} 条")
        st.dataframe(df_ht, use_container_width=True, hide_index=True)

    with ref_sub4:
        st.subheader("龙虎榜")
        dragon_date = st.date_input("选择日期", value=datetime.now() - timedelta(days=1))
        df_top = query(
            "SELECT t.ts_code, t.name, t.pct_change, t.net_amount, t.l_buy, t.l_sell, t.reason FROM top_list t WHERE t.trade_date=? ORDER BY ABS(t.net_amount) DESC",
            (dragon_date.strftime("%Y%m%d"),)
        )
        if df_top.empty:
            st.info(f"{dragon_date} 无龙虎榜数据（非交易日或未同步）")
        else:
            st.caption(f"{dragon_date} 共 {len(df_top)} 只股票上榜")
            st.dataframe(df_top, use_container_width=True, hide_index=True)

    with ref_sub5:
        st.subheader("融资融券余额")
        wl_mg = query("SELECT ts_code, stock_name FROM watchlist")
        mg_options = [f"{r['ts_code']} {r['stock_name']}" for _, r in wl_mg.iterrows()] if not wl_mg.empty else []
        sel_mg = st.selectbox("选择股票", mg_options, key="mg_stock") if mg_options else st.text_input("输入代码", key="mg_code")
        ts_mg = sel_mg.split()[0] if sel_mg and " " in sel_mg else sel_mg

        df_mg = query(
            "SELECT trade_date, rzye, rqye, rzrqye, rzmre FROM margin WHERE ts_code=? ORDER BY trade_date DESC LIMIT 60",
            (ts_mg,)
        )
        if df_mg.empty:
            st.info("暂无融资融券数据")
        else:
            st.line_chart(df_mg.set_index("trade_date")["rzye"].iloc[::-1])
            with st.expander("明细"):
                st.dataframe(df_mg, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════
# Tab 7: 特色数据
# ══════════════════════════════════════════════════════════
with tab_special:
    sp_sub1, sp_sub2, sp_sub3, sp_sub4, sp_sub5 = st.tabs([
        "🏷️ 概念板块", "🧩 筹码分布", "🔬 机构调研", "📣 盈利预测", "🏦 券商金股"
    ])

    with sp_sub1:
        st.subheader("概念板块查询")
        c1, c2 = st.columns([2, 1])
        concept_kw = c1.text_input("搜索概念", placeholder="如 ChatGPT、半导体、新能源")
        view_mode  = c2.radio("查看模式", ["概念列表", "查成分股"], horizontal=True)

        if view_mode == "概念列表":
            df_concept = query(
                "SELECT concept_code, concept_name, (SELECT COUNT(*) FROM concept_detail cd WHERE cd.concept_code=c.concept_code) as 成分数 FROM concept c WHERE concept_name LIKE ? ORDER BY 成分数 DESC",
                (f"%{concept_kw}%",)
            )
            st.caption(f"共 {len(df_concept)} 个概念")
            st.dataframe(df_concept, use_container_width=True, hide_index=True)
        else:
            df_concept2 = query(
                "SELECT concept_code, concept_name FROM concept WHERE concept_name LIKE ? ORDER BY concept_name LIMIT 50",
                (f"%{concept_kw}%",)
            )
            if df_concept2.empty:
                st.info("未找到相关概念")
            else:
                sel_concept = st.selectbox("选择概念", df_concept2["concept_name"].tolist())
                code_row = df_concept2[df_concept2["concept_name"] == sel_concept].iloc[0]
                df_members = query(
                    "SELECT cd.ts_code, cd.name, s.area, s.industry, s.market FROM concept_detail cd LEFT JOIN stock_basic s ON cd.ts_code=s.ts_code WHERE cd.concept_code=? ORDER BY cd.ts_code",
                    (code_row["concept_code"],)
                )
                st.caption(f"「{sel_concept}」共 {len(df_members)} 只成分股")
                st.dataframe(df_members, use_container_width=True, hide_index=True)

    with sp_sub2:
        st.subheader("筹码分布分析")
        wl_cyq = query("SELECT ts_code, stock_name FROM watchlist")
        cyq_options = [f"{r['ts_code']} {r['stock_name']}" for _, r in wl_cyq.iterrows()] if not wl_cyq.empty else []
        sel_cyq = st.selectbox("选择股票", cyq_options, key="cyq_stock") if cyq_options else st.text_input("输入代码", key="cyq_code")
        ts_cyq = sel_cyq.split()[0] if sel_cyq and " " in sel_cyq else sel_cyq

        df_cyq = query(
            "SELECT trade_date, winner_rate, cost_5pct, cost_15pct, cost_50pct, cost_85pct, cost_95pct FROM cyq_perf WHERE ts_code=? ORDER BY trade_date DESC LIMIT 10",
            (ts_cyq,)
        )
        if df_cyq.empty:
            st.info("暂无筹码数据，请执行 hub-weekly 同步")
        else:
            latest_cyq = df_cyq.iloc[0]
            c1, c2, c3 = st.columns(3)
            c1.metric("获利盘比例", f"{latest_cyq['winner_rate']:.1f}%" if pd.notna(latest_cyq.get('winner_rate')) else "—")
            c2.metric("50%集中成本", f"{latest_cyq['cost_50pct']:.2f}" if pd.notna(latest_cyq.get('cost_50pct')) else "—")
            c3.metric("95%集中成本", f"{latest_cyq['cost_95pct']:.2f}" if pd.notna(latest_cyq.get('cost_95pct')) else "—")

            st.caption("筹码成本分布（不同百分位）")
            chart_data = df_cyq[["trade_date", "cost_5pct", "cost_15pct", "cost_50pct", "cost_85pct", "cost_95pct"]].set_index("trade_date").iloc[::-1]
            st.line_chart(chart_data)
            st.dataframe(df_cyq, use_container_width=True, hide_index=True)

    with sp_sub3:
        st.subheader("机构调研记录")
        wl_surv = query("SELECT ts_code, stock_name FROM watchlist")
        surv_options = [f"{r['ts_code']} {r['stock_name']}" for _, r in wl_surv.iterrows()] if not wl_surv.empty else []
        sel_surv = st.selectbox("选择股票", surv_options, key="surv_stock") if surv_options else st.text_input("输入代码", key="surv_code")
        ts_surv = sel_surv.split()[0] if sel_surv and " " in sel_surv else sel_surv

        df_surv = query(
            "SELECT surv_date, org_name, org_type, rece_mode, num_org FROM stk_surv WHERE ts_code=? ORDER BY surv_date DESC LIMIT 50",
            (ts_surv,)
        )
        if df_surv.empty:
            st.info("暂无机构调研数据")
        else:
            st.caption(f"共 {len(df_surv)} 条调研记录")
            st.dataframe(df_surv, use_container_width=True, hide_index=True)

    with sp_sub4:
        st.subheader("机构盈利预测（一致预期）")
        wl_rc = query("SELECT ts_code, stock_name FROM watchlist")
        rc_options = [f"{r['ts_code']} {r['stock_name']}" for _, r in wl_rc.iterrows()] if not wl_rc.empty else []
        sel_rc = st.selectbox("选择股票", rc_options, key="rc_stock") if rc_options else st.text_input("输入代码", key="rc_code")
        ts_rc = sel_rc.split()[0] if sel_rc and " " in sel_rc else sel_rc

        df_rc = query(
            "SELECT report_date, org_name, eps, pe, rating, target_price FROM report_rc WHERE ts_code=? ORDER BY report_date DESC LIMIT 30",
            (ts_rc,)
        )
        if df_rc.empty:
            st.info("暂无盈利预测数据")
        else:
            # 评级分布
            rating_counts = df_rc["rating"].value_counts()
            c1, c2 = st.columns([1, 2])
            with c1:
                st.caption("评级分布")
                for r, cnt in rating_counts.items():
                    color = "🟢" if "买" in str(r) or "增持" in str(r) else ("🔴" if "卖" in str(r) or "减持" in str(r) else "🟡")
                    st.write(f"{color} {r}: {cnt}家")
            with c2:
                st.caption("目标价分布")
                if df_rc["target_price"].notna().any():
                    tp = df_rc["target_price"].dropna()
                    st.write(f"均值 {tp.mean():.2f} | 最高 {tp.max():.2f} | 最低 {tp.min():.2f}")
            st.dataframe(df_rc, use_container_width=True, hide_index=True)

    with sp_sub5:
        st.subheader("券商金股推荐")
        df_br = query(
            "SELECT month, broker, ts_code, name, reason FROM broker_recommend ORDER BY month DESC LIMIT 100"
        )
        if df_br.empty:
            st.info("暂无券商金股数据，请执行 hub-weekly 同步")
        else:
            months = df_br["month"].unique().tolist()
            sel_month = st.selectbox("选择月份", months)
            df_br_m = df_br[df_br["month"] == sel_month]
            st.caption(f"{sel_month} 共 {len(df_br_m)} 条推荐")
            st.dataframe(df_br_m, use_container_width=True, hide_index=True)
