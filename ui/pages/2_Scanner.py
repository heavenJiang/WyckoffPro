"""
ui/pages/2_Scanner.py
"""
import streamlit as st
import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from main import daily_analysis_pipeline, storage

st.set_page_config(page_title="Scanner - WyckoffPro", page_icon="🔍")
st.title("🔍 每日信号扫描")
st.write("点击按钮，系统将自动依次扫描所有自选股，拉取最新数据，执行信号检测及AI证伪。")

if st.button("🚀 开始全量扫描 (Daily Pipeline)", type="primary"):
    wl = storage.get_watchlist()
    if not wl:
        st.warning("暂无自选股。")
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        for i, w in enumerate(wl):
            code = w["stock_code"]
            name = w.get("name", "")
            status_text.text(f"正在扫描: {code} {name} ... ({i+1}/{len(wl)})")
            
            try:
                # 运行全量分析 pipeline
                res = asyncio.run(daily_analysis_pipeline(code))
                if "error" in res:
                    st.error(f"{code} 扫描失败: {res['error']}")
                else:
                    results.append(res)
            except Exception as e:
                st.error(f"{code} 发生异常: {e}")
                
            progress_bar.progress((i + 1) / len(wl))
            
        status_text.text("扫描完成！")
        st.success("所有自选股已扫描完毕。")
        
        # 显示结果概览
        if results:
            st.subheader("今日扫描信号概览")
            for r in results:
                code = r["stock_code"]
                advice = r.get("advice", {}).get("advice_type", "WAIT")
                conf = r.get("advice", {}).get("confidence", 0)
                phase = r.get("phase", "UNKNOWN")
                sigs = ", ".join([s["signal_type"] for s in r.get("signals", [])]) if r.get("signals") else "无"
                
                with st.expander(f"[{code}] 建议: {advice} ({conf}%) | 阶段: {phase} | 信号: {sigs}"):
                    if r.get("alerts"):
                        for alert in r.get("alerts"):
                            st.warning(f"⚠️ {alert.get('message')}")
                    st.write(r.get("advice", {}).get("summary", ""))
