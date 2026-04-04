"""
ui/pages/4_Plans.py
"""
import streamlit as st
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from main import storage

st.set_page_config(page_title="Trade Plans - WyckoffPro", page_icon="📝")
st.title("📝 交易计划与持仓")

tab1, tab2 = st.tabs(["待执行计划 (DRAFT)", "当前持仓 (OPEN)"])

with tab1:
    st.subheader("由最新AI建议生成的交易计划")
    with storage._get_conn() as conn:
        cursor = conn.execute("SELECT * FROM trade_plan WHERE status='DRAFT' ORDER BY updated_at DESC")
        cols = [description[0] for description in cursor.description]
        plans = [dict(zip(cols, row)) for row in cursor.fetchall()]

    if not plans:
        st.info("暂无待执行的交易计划。")
    else:
        for p in plans:
            with st.expander(f"{p['direction']} - {p['stock_code']} | 入场: {p['entry_price']}", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("入场价", p["entry_price"])
                c2.metric("止损", p["stop_loss"])
                c3.metric("目标", p["target_1"])
                c4.metric("盈亏比", p["rr_ratio"])
                
                st.write(p.get("notes", ""))
                
                # 动作按钮
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ 记录为已开仓", key=f"open_{p['id']}"):
                        # 简化处理：更新状态并开仓
                        storage.execute("UPDATE trade_plan SET status='EXECUTED' WHERE id=?", (p["id"],))
                        storage.save_position({
                            "stock_code": p["stock_code"],
                            "stock_name": "", # 省略名称
                            "direction": p["direction"],
                            "quantity": 100, # 默认
                            "cost_price": p["entry_price"],
                            "current_price": p["entry_price"],
                            "status": "OPEN",
                            "notes": "由计划生成"
                        })
                        st.success("已转为持仓！请刷新页面。")
                with col2:
                    if st.button("❌ 废弃该计划", key=f"drop_{p['id']}"):
                        storage.execute("UPDATE trade_plan SET status='CANCELLED' WHERE id=?", (p["id"],))
                        st.success("计划已废弃！请刷新页面。")

with tab2:
    st.subheader("持仓台账")
    positions = storage.get_positions()
    if not isinstance(positions, list):
        positions = []
        
    open_pos = [p for p in positions if p.get("status") == "OPEN"]
    
    if not open_pos:
        st.info("当前无持仓。")
    else:
        df = pd.DataFrame(open_pos)
        df["unrealized_pnl"] = (df["current_price"] - df["cost_price"]) * df["quantity"]
        df["pnl_pct"] = (df["current_price"] - df["cost_price"]) / df["cost_price"] * 100
        
        st.dataframe(
            df[["stock_code", "direction", "cost_price", "current_price", "quantity", "unrealized_pnl", "pnl_pct"]].style.format({
                "cost_price": "{:.2f}",
                "current_price": "{:.2f}",
                "unrealized_pnl": "{:.2f}",
                "pnl_pct": "{:.2f}%"
            }),
            use_container_width=True
        )
