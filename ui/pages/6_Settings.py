"""
ui/pages/6_Settings.py
"""
import streamlit as st
import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from main import storage

st.set_page_config(page_title="Settings - WyckoffPro", page_icon="⚙️")
st.title("⚙️ 系统设置")

tab1, tab2 = st.tabs(["自选股管理 (Watchlist)", "系统参数"])

with tab1:
    st.subheader("当前自选股")
    wl = storage.get_watchlist()
    
    if wl:
        for w in wl:
            col1, col2, col3, col4 = st.columns([2, 3, 3, 2])
            col1.write(f"**{w['stock_code']}**")
            col2.write(w.get("stock_name", ""))
            col3.write(w.get("added_at", "-"))
            if col4.button("删除", key=f"del_{w['stock_code']}"):
                with storage._get_conn() as conn:
                    conn.execute("DELETE FROM watchlist WHERE stock_code=?", (w['stock_code'],))
                st.success(f"已删除 {w['stock_code']}")
                st.rerun()
    else:
        st.info("自选股为空")

    st.divider()
    st.subheader("添加自选股")
    new_code = st.text_input("股票代码 (如 000001.SZ, 600519.SH)")
    new_name = st.text_input("股票名称")
    if st.button("➕ 添加"):
        if new_code:
            try:
                storage.add_to_watchlist(new_code, new_name)
                st.success("添加成功！")
                st.rerun()
            except Exception as e:
                st.error(f"添加失败: {e}")

with tab2:
    st.subheader("配置文件 (config/default.yaml)")
    st.info("目前配置只能通过手动修改 config/default.yaml 文件进行，系统支持在下次运行时自动生效。")
    
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../config/default.yaml'))
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()
        st.code(content, language="yaml")
    else:
        st.error(f"配置文件未找到: {config_path}")
