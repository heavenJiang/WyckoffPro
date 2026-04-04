"""
ui/app.py — Streamlit UI 入口文件
使用方法: pip install streamlit && streamlit run ui/app.py
"""
import streamlit as st
import sys
import os

# 将项目根目录加入模块搜索路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

st.set_page_config(
    page_title="WyckoffPro V3.1 交易系统",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.sidebar.markdown("## 📈 WyckoffPro V3.1")
st.sidebar.markdown("基于威科夫方法的AI增强分析系统")
st.sidebar.divider()

st.markdown("""
# 欢迎使用 WyckoffPro V3.1
本系统融合了经典的孟洪涛《威科夫操盘法》与现代AI证伪技术，提供全面的个股量价分析。

### 主要功能
- **Dashboard 总览**: 查看大盘状态和个人自选股追踪
- **Scanner 自动扫描**: 每日收盘后扫描整个股票池，发现潜在威科夫信号
- **Analysis 深度分析**: 查看单只股票的K线、点数图、反面证据及AI深度建议
- **Plans 交易计划**: 查看基于AI建议和风控自动生成的交易计划
- **Backtest 历史回测**: 根据历史信号评估策略有效性
- **Settings 系统设置**: 配置AI API、数据源等

👈 请从左侧边栏选择功能面开始。
""")
