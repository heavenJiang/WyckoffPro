"""
ui/app.py — WyckoffPro 主页（首页 + Dashboard 合并）
"""
import streamlit as st
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from main import config
from data.storage import DataStorage
from ui.components.glossary import tip, md_tip
from ui.components.translations import CN

st.set_page_config(
    page_title="WyckoffPro V3.1 交易系统",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.sidebar.markdown("## 📈 WyckoffPro V3.1")
st.sidebar.markdown("基于威科夫方法的AI增强分析系统")
st.sidebar.divider()

@st.cache_resource
def get_storage():
    return DataStorage(config["data"].get("db_path", "wyckoffpro.db"))

storage = get_storage()

st.title("📊 WyckoffPro V3.1 — 总览 Dashboard")

# ── 自选股追踪 ──────────────────────────────────────────
wl = storage.get_watchlist()

if not wl:
    st.warning("自选股列表为空，请前往 **Settings** 页面添加。")
else:
    st.subheader("自选股追踪")

    drafts_count = len(storage.get_trade_plans(status="DRAFT"))
    open_pos_count = len(storage.get_positions(status="OPEN"))
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("监控股票数", len(wl))
    col2.metric("待执行计划", drafts_count,
                help="有交易计划等待开仓确认，点击右侧链接前往处理")
    col3.metric("模拟持仓数", open_pos_count)
    with col4:
        st.write("")
        st.page_link("pages/4_Plans.py", label="📋 前往交易计划 →", icon="📋")

    data = []
    for w in wl:
        code = w["stock_code"]
        phase = storage.get_current_phase(code, "daily")
        phase_str = phase.get("phase_code", "UNKNOWN") if phase else "UNKNOWN"
        adv = storage.get_latest_advice(code)
        adv_type = adv.get("advice_type", "WAIT") if adv else "WAIT"
        adv_conf = adv.get("confidence", 0) if adv else 0
        adv_date = adv.get("created_at", "N/A")[:10] if adv else "N/A"
        data.append({
            "代码": code,
            "名称": w.get("stock_name", ""),
            "当前阶段": CN.phase(phase_str),
            "最新建议": f"{CN.advice_icon(adv_type)} {CN.advice(adv_type)} ({adv_conf}%)",
            "更新日期": adv_date,
        })

    if data:
        df = pd.DataFrame(data)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "当前阶段": st.column_config.TextColumn("当前阶段", help=tip("威科夫阶段")),
                "最新建议": st.column_config.TextColumn("最新建议", help="强烈买入/买入=做多信号，关注=持续观察，持有=保持仓位，等待=暂无机会，减仓/卖出=做空/离场信号；括号内为置信度"),
            },
        )

st.divider()

# ── 功能导航说明 ────────────────────────────────────────
st.subheader("功能导航")
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f"**🔍 Scanner 自动扫描**\n\n每日收盘后扫描整个股票池，发现潜在{md_tip('威科夫方法', '威科夫')}信号", unsafe_allow_html=True)
    st.markdown(f"**📐 Analysis 深度分析**\n\n查看单只股票 K线、{md_tip('点数图')}、反面证据及AI深度建议", unsafe_allow_html=True)
with c2:
    st.markdown("**📋 Plans 交易计划**\n\n基于AI建议和风控自动生成的交易计划")
    st.markdown("**🧪 Backtest 历史回测**\n\n根据历史信号评估策略有效性")
with c3:
    st.markdown("**🗄️ DataHub 数据仓库**\n\n全量 Tushare 数据，含日线、财务、宏观、概念等25+张表")
    st.markdown("**⚙️ Settings 系统设置**\n\n配置 AI API、数据源、自选股等")
