"""
ui/pages/1_Dashboard.py
"""
import streamlit as st
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from data.storage import DataStorage
from main import config

st.set_page_config(page_title="Dashboard - WyckoffPro", page_icon="📊", layout="wide")
st.title("📊 概览 Dashboard")

# 初始化存储组件
@st.cache_resource
def get_storage():
    return DataStorage(config["data"].get("db_path", "wyckoffpro.db"))

storage = get_storage()

# 获取自选股和最近分析结果
wl = storage.get_watchlist()
if not wl:
    st.warning("自选股列表为空，请前往设置页面添加。")
    st.stop()

st.subheader("自选股追踪")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("监控总数", len(wl))

# 显示自选股列表（含最新状态）
data = []
for w in wl:
    code = w["stock_code"]
    phase = storage.get_current_phase(code, "daily")
    phase_str = phase.get("phase_code", "UNKNOWN") if phase else "UNKNOWN"
    
    # 获取最新的AI建议
    adv = storage.get_latest_advice(code)
    
    adv_type = adv.get("advice_type", "WAIT") if adv else "WAIT"
    adv_conf = adv.get("confidence", 0) if adv else 0
    adv_date = adv.get("created_at", "N/A")[:10] if adv else "N/A"
    
    data.append({
        "代码": code,
        "名称": w.get("stock_name", ""),
        "当前阶段": phase_str,
        "最新建议": f"{adv_type} ({adv_conf}%)",
        "更新日期": adv_date
    })

if data:
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
