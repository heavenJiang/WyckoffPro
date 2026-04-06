"""
ui/pages/4_Plans.py — 交易计划与模拟持仓
"""
import streamlit as st
import sys, os, sqlite3
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from main import storage, config
from ui.components.glossary import tip
from ui.components.translations import CN

st.set_page_config(page_title="Trade Plans - WyckoffPro", page_icon="📋", layout="wide")

DB_PATH = config["data"].get("db_path", "data/wyckoffpro.db")


# ── 工具函数 ──────────────────────────────────────────────────────────────
def get_latest_close(stock_code: str) -> float:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT close FROM kline_daily WHERE stock_code=? ORDER BY trade_date DESC LIMIT 1",
                (stock_code,)
            ).fetchone()
        return float(row[0]) if row else 0.0
    except Exception:
        return 0.0


def get_linked_advice(advice_id) -> dict:
    if not advice_id:
        return {}
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT advice_type,confidence,summary,reasoning,invalidation,"
                "counter_evidence_score,falsification_gate FROM advice WHERE id=?",
                (int(advice_id),)
            ).fetchone()
        return dict(row) if row else {}
    except Exception:
        return {}


def rr_color(rr) -> str:
    if rr is None:
        return "#9ca3af"
    try:
        v = float(rr)
        return "#4ade80" if v >= 2.5 else ("#fbbf24" if v >= 1.5 else "#f87171")
    except Exception:
        return "#9ca3af"


def pnl_color(pct: float) -> str:
    return "#ef4444" if pct < 0 else "#22c55e"


# ── 页面标题与快速统计 ─────────────────────────────────────────────────────
st.title("📋 交易计划与模拟持仓")

drafts   = storage.get_trade_plans(status="DRAFT")
open_pos = storage.get_positions(status="OPEN")

hd1, hd2, hd3, hd4 = st.columns(4)
hd1.metric("待执行计划", len(drafts),
           help="状态为 DRAFT 的交易计划，等待手动确认开仓")
hd2.metric("模拟持仓数", len(open_pos),
           help="当前未平仓的模拟持仓记录")
total_pnl = sum(
    (get_latest_close(p["stock_code"]) - p.get("cost_price", 0)) * p.get("quantity", 0)
    for p in open_pos
)
hd3.metric("持仓总浮盈", f"¥{total_pnl:+.0f}")
closed = storage.get_positions(status="CLOSED")
hd4.metric("历史已平仓", len(closed))

st.divider()

# ── Tab 布局 ──────────────────────────────────────────────────────────────
tab_draft, tab_new, tab_pos, tab_hist = st.tabs([
    f"📝 待执行计划 ({len(drafts)})",
    "✏️ 手动建计划",
    f"💼 模拟持仓 ({len(open_pos)})",
    "📜 历史记录",
])


# ══════════════════════════════════════════════════════════════════════════
# Tab 1: 待执行计划 (DRAFT)
# ══════════════════════════════════════════════════════════════════════════
with tab_draft:
    if not drafts:
        st.info("暂无待执行计划。")
        st.caption("计划来源：① Analysis 页面「刷新分析」后自动生成  ② 手动建计划（见上方标签页）")
        st.page_link("pages/3_Analysis.py", label="→ 前往 Analysis 运行分析", icon="🔬")
    else:
        st.caption(f"共 {len(drafts)} 条待确认计划，选择开仓后将转入模拟持仓。")
        for p in drafts:
            adv          = get_linked_advice(p.get("linked_advice_id"))
            latest_close = get_latest_close(p["stock_code"])
            price_delta  = round(latest_close - p["entry_price"], 2) if latest_close else None
            adv_type     = adv.get("advice_type", "—")
            gate         = adv.get("falsification_gate", "PASS")
            rr           = p.get("rr_ratio")

            header = (
                f"{CN.advice_icon(adv_type)} **{p['stock_code']} {p.get('stock_name','')}**"
                f" | {p.get('direction','LONG')} | 入场 ¥{p['entry_price']}"
                f" | 现价 {f'¥{latest_close:.2f}' if latest_close else '—'}"
                f" | 生成于 {str(p.get('created_at',''))[:10]}"
            )

            with st.expander(header, expanded=True):
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("入场价",  f"¥{p['entry_price']:.2f}",
                          delta=f"{price_delta:+.2f}" if price_delta is not None else None)
                m2.metric("止损价",  f"¥{p['stop_loss']:.2f}" if p.get("stop_loss") else "—",
                          help=tip("止损"))
                m3.metric("目标1",   f"¥{p['target_1']:.2f}" if p.get("target_1") else "—")
                m4.metric("目标2",   f"¥{p['target_2']:.2f}" if p.get("target_2") else "—")
                m5.metric("盈亏比",  f"{rr}x" if rr else "—", help=tip("RR"))

                if adv:
                    ac1, ac2, ac3, ac4 = st.columns(4)
                    ac1.write(f"建议 {CN.advice_icon(adv_type)} **{CN.advice(adv_type)}**")
                    ac2.write(f"置信度 **{adv.get('confidence',0):.0f}%**")
                    ac3.metric("反面积分", adv.get("counter_evidence_score", 0))
                    gate_cn, _ = CN.gate(gate)
                    ac4.metric("证伪门控", gate_cn)
                    if adv.get("summary"):
                        st.caption(f"📝 {adv['summary']}")
                    if adv.get("invalidation"):
                        st.warning(f"失效条件：{adv['invalidation']}")

                if p.get("notes"):
                    st.caption(p["notes"])

                st.page_link("pages/3_Analysis.py",
                             label=f"🔬 查看 {p['stock_code']} 完整分析", icon="🔬")
                st.markdown("---")

                # ── 操作区 ──
                op1, op2, op3 = st.columns([2, 2, 1])
                with op1:
                    qty = st.number_input(
                        "买入股数（手=100股）", min_value=100, step=100,
                        value=100, key=f"qty_{p['id']}"
                    )
                    exec_price = st.number_input(
                        "实际成交价（默认用入场价）",
                        value=float(p["entry_price"]),
                        step=0.01, key=f"ep_{p['id']}"
                    )
                    if st.button("✅ 确认开仓 → 转为持仓", key=f"open_{p['id']}", type="primary"):
                        storage.update_trade_plan_status(p["id"], "EXECUTED")
                        storage.save_position({
                            "stock_code":   p["stock_code"],
                            "stock_name":   p.get("stock_name", ""),
                            "direction":    p.get("direction", "LONG"),
                            "quantity":     qty,
                            "cost_price":   exec_price,
                            "current_price": latest_close or exec_price,
                            "status":       "OPEN",
                            "stop_loss":    p.get("stop_loss"),
                            "target_price": p.get("target_1"),
                            "plan_id":      p["id"],
                            "notes":        f"来自计划#{p['id']}",
                        })
                        st.success(f"已开仓 {qty}股 @ ¥{exec_price}，转入模拟持仓！")
                        st.rerun()
                with op2:
                    st.write("")
                    st.write("")
                    new_sl = st.number_input(
                        "调整止损价", value=float(p.get("stop_loss") or 0),
                        step=0.01, key=f"nsl_{p['id']}"
                    )
                    if st.button("🔧 更新止损", key=f"upsl_{p['id']}"):
                        with sqlite3.connect(DB_PATH) as conn:
                            conn.execute(
                                "UPDATE trade_plan SET stop_loss=? WHERE id=?",
                                (new_sl, p["id"])
                            )
                        st.success("止损已更新")
                        st.rerun()
                with op3:
                    st.write("")
                    st.write("")
                    st.write("")
                    st.write("")
                    if st.button("❌ 废弃", key=f"drop_{p['id']}"):
                        storage.update_trade_plan_status(p["id"], "CANCELLED")
                        st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# Tab 2: 手动建计划
# ══════════════════════════════════════════════════════════════════════════
with tab_new:
    st.markdown("### 手动创建交易计划")
    st.caption("手动输入参数建立计划，或基于分析结果微调后存入。")

    wl = storage.get_watchlist()
    wl_options = {w["stock_code"]: f"{w['stock_code']} - {w.get('stock_name','')}" for w in wl}

    fc1, fc2 = st.columns(2)
    with fc1:
        use_watchlist = st.checkbox("从自选股选择", value=True)
        if use_watchlist and wl_options:
            sel_code = st.selectbox("股票", list(wl_options.keys()),
                                    format_func=lambda x: wl_options[x])
            sel_name = wl_options.get(sel_code, "").split(" - ")[-1]
        else:
            sel_code = st.text_input("股票代码", placeholder="如 300027.SZ")
            sel_name = st.text_input("股票名称", placeholder="可选")

        direction = st.radio("方向", ["LONG（做多）", "SHORT（做空）"],
                             horizontal=True)
        direction_val = "LONG" if "LONG" in direction else "SHORT"

        current_p = get_latest_close(sel_code) if sel_code else 0.0
        if current_p:
            st.caption(f"最新收盘价：¥{current_p:.2f}")

    with fc2:
        entry_p  = st.number_input("入场价 ¥", value=current_p or 0.0, step=0.01, min_value=0.0)
        stop_p   = st.number_input("止损价 ¥", value=round(entry_p * 0.95, 2) if entry_p else 0.0,
                                   step=0.01, min_value=0.0)
        target1  = st.number_input("目标价1 ¥", value=round(entry_p * 1.15, 2) if entry_p else 0.0,
                                   step=0.01, min_value=0.0)
        target2  = st.number_input("目标价2 ¥（可选）", value=0.0, step=0.01, min_value=0.0)

        # 实时计算 RR
        if entry_p > 0 and stop_p > 0 and target1 > 0:
            risk   = abs(entry_p - stop_p)
            reward = abs(target1 - entry_p)
            rr_val = round(reward / risk, 2) if risk > 0 else 0
            rr_clr = rr_color(rr_val)
            st.markdown(
                f'<span style="color:{rr_clr};font-size:16px;font-weight:700;">'
                f'盈亏比 RR = {rr_val}x</span>',
                unsafe_allow_html=True
            )
        else:
            rr_val = None

    notes = st.text_area("备注", placeholder="交易逻辑、触发条件、关注点…", height=80)

    if st.button("💾 保存计划", type="primary"):
        if not sel_code:
            st.error("请输入股票代码")
        elif entry_p <= 0 or stop_p <= 0 or target1 <= 0:
            st.error("入场价、止损价、目标价均需大于0")
        else:
            plan = {
                "stock_code":      sel_code,
                "direction":       direction_val,
                "entry_mode":      "手动",
                "entry_price":     entry_p,
                "stop_loss":       stop_p,
                "target_1":        target1,
                "target_2":        target2 if target2 > 0 else None,
                "rr_ratio":        rr_val,
                "position_pct":    None,
                "status":          "DRAFT",
                "linked_advice_id": None,
                "notes":           notes,
            }
            new_id = storage.save_trade_plan(plan)
            st.success(f"计划已保存（ID #{new_id}），可在「待执行计划」中确认开仓。")
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# Tab 3: 模拟持仓
# ══════════════════════════════════════════════════════════════════════════
with tab_pos:
    if not open_pos:
        st.info("当前无模拟持仓。在「待执行计划」中确认开仓后将出现在这里。")
    else:
        # ── 刷新最新价 & 汇总 ──
        refreshed = []
        for pos in open_pos:
            latest = get_latest_close(pos["stock_code"])
            if latest and latest != pos.get("current_price"):
                pos["current_price"] = latest
                storage.save_position(pos)
            pos["_float_pnl"] = (pos["current_price"] - pos["cost_price"]) * pos["quantity"]
            pos["_pnl_pct"]   = (pos["current_price"] - pos["cost_price"]) / pos["cost_price"] * 100
            refreshed.append(pos)

        total_pnl = sum(p["_float_pnl"] for p in refreshed)
        win_n     = sum(1 for p in refreshed if p["_float_pnl"] > 0)
        total_cost = sum(p["cost_price"] * p["quantity"] for p in refreshed)

        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("持仓数",   len(refreshed))
        sc2.metric("总浮动盈亏", f"¥{total_pnl:+.0f}")
        sc3.metric("投入市值",  f"¥{total_cost:,.0f}")
        sc4.metric("盈利笔 / 总",  f"{win_n}/{len(refreshed)}")

        st.divider()

        # ── 逐笔持仓卡片 ──
        for pos in refreshed:
            cp   = pos["current_price"]
            ep   = pos["cost_price"]
            sl   = pos.get("stop_loss")
            tp   = pos.get("target_price")
            pnl  = pos["_float_pnl"]
            pct  = pos["_pnl_pct"]
            pclr = pnl_color(pct)

            # 止损 / 目标距离
            sl_dist = f"{(cp - sl) / cp * 100:+.1f}%" if sl and cp else "—"
            tp_dist = f"{(tp - cp) / cp * 100:+.1f}%" if tp and cp else "—"

            with st.expander(
                f"**{pos['stock_code']} {pos.get('stock_name','')}** "
                f"| {pos.get('direction','LONG')} "
                f"| {pos['quantity']}股 @ ¥{ep:.2f} "
                f"| 浮盈 {'🟢' if pnl>=0 else '🔴'} ¥{pnl:+.0f} ({pct:+.1f}%)",
                expanded=True,
            ):
                # 核心指标行
                pi1, pi2, pi3, pi4, pi5, pi6 = st.columns(6)
                pi1.metric("成本价",   f"¥{ep:.2f}")
                pi2.metric("现价",     f"¥{cp:.2f}",
                           delta=f"{cp - ep:+.2f}")
                pi3.metric("浮动盈亏", f"¥{pnl:+.0f}",
                           delta=f"{pct:+.1f}%")
                pi4.metric("止损价",   f"¥{sl:.2f}" if sl else "未设",
                           delta=f"距止损 {sl_dist}" if sl else None,
                           delta_color="inverse")
                pi5.metric("目标价",   f"¥{tp:.2f}" if tp else "未设",
                           delta=f"距目标 {tp_dist}" if tp else None)
                pi6.metric("开仓日",   str(pos.get("open_date", "—"))[:10])

                # 进度条：止损→成本→目标
                if sl and tp and ep:
                    full_range = tp - sl
                    if full_range > 0:
                        progress = max(0, min(1, (cp - sl) / full_range))
                        st.markdown(
                            f'<div style="margin:4px 0 2px;font-size:11px;color:#6b7280;">'
                            f'止损 ¥{sl:.2f}'
                            f'<span style="float:right;">目标 ¥{tp:.2f}</span></div>'
                            f'<div style="background:#2a2a2a;border-radius:4px;height:6px;">'
                            f'<div style="width:{progress*100:.1f}%;height:100%;'
                            f'background:{"#22c55e" if progress>0.5 else "#fbbf24"};'
                            f'border-radius:4px;"></div></div>',
                            unsafe_allow_html=True
                        )

                if pos.get("notes"):
                    with st.expander("备注记录", expanded=False):
                        st.text(pos["notes"])

                st.markdown("---")
                # ── 操作 ──
                op_a, op_b, op_c = st.columns(3)

                with op_a:
                    st.markdown("**🔧 调整止损/目标**")
                    new_sl = st.number_input(
                        "新止损价", value=float(sl or ep * 0.95),
                        step=0.01, key=f"sl_{pos['id']}"
                    )
                    new_tp = st.number_input(
                        "新目标价", value=float(tp or ep * 1.15),
                        step=0.01, key=f"tp_{pos['id']}"
                    )
                    if st.button("保存调整", key=f"adj_{pos['id']}"):
                        pos["stop_loss"]    = new_sl
                        pos["target_price"] = new_tp
                        storage.save_position(pos)
                        st.success("已更新止损/目标")
                        st.rerun()

                with op_b:
                    st.markdown("**📤 部分平仓**")
                    close_qty = st.number_input(
                        "平仓股数", min_value=100, max_value=pos["quantity"],
                        step=100, value=min(100, pos["quantity"]),
                        key=f"cq_{pos['id']}"
                    )
                    close_price = st.number_input(
                        "平仓价", value=float(cp),
                        step=0.01, key=f"cp_{pos['id']}"
                    )
                    close_note = st.text_input("备注", key=f"cn_{pos['id']}")
                    if st.button(f"平仓 {close_qty}股", key=f"pc_{pos['id']}"):
                        pnl_this = (close_price - ep) * close_qty
                        storage.partial_close_position(
                            pos["id"], close_qty, close_price, close_note
                        )
                        st.success(f"已平仓 {close_qty}股 @ ¥{close_price}，"
                                   f"本次盈亏 ¥{pnl_this:+.0f}")
                        st.rerun()

                with op_c:
                    st.markdown("**🚪 全部平仓**")
                    full_close_p = st.number_input(
                        "平仓价", value=float(cp),
                        step=0.01, key=f"fcp_{pos['id']}"
                    )
                    if st.button("全部平仓", key=f"fc_{pos['id']}", type="primary"):
                        total_pnl_this = (full_close_p - ep) * pos["quantity"]
                        storage.partial_close_position(
                            pos["id"], pos["quantity"], full_close_p, "全部平仓"
                        )
                        st.success(f"全部平仓完成，盈亏 ¥{total_pnl_this:+.0f}")
                        st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# Tab 4: 历史记录
# ══════════════════════════════════════════════════════════════════════════
with tab_hist:
    sub1, sub2 = st.tabs(["📦 已平仓记录", "🗂️ 历史计划"])

    with sub1:
        closed_pos = storage.get_positions(status="CLOSED")
        if not closed_pos:
            st.info("暂无已平仓记录。")
        else:
            rows = []
            for pos in closed_pos:
                ep  = pos.get("cost_price", 0)
                cp2 = pos.get("close_price") or pos.get("current_price") or ep
                qty = pos.get("quantity", 0)
                pnl = (cp2 - ep) * qty
                pct = (cp2 - ep) / ep * 100 if ep else 0
                rows.append({
                    "代码":   pos["stock_code"],
                    "名称":   pos.get("stock_name", ""),
                    "方向":   pos.get("direction", "LONG"),
                    "数量":   qty,
                    "成本价": ep,
                    "平仓价": cp2,
                    "盈亏":   round(pnl, 2),
                    "盈亏%":  round(pct, 2),
                    "开仓日": str(pos.get("open_date", ""))[:10],
                    "平仓日": str(pos.get("close_date", ""))[:10],
                })
            df_closed = pd.DataFrame(rows)
            total_pnl_hist = df_closed["盈亏"].sum()
            win_rate_hist  = (df_closed["盈亏"] > 0).mean() * 100
            hc1, hc2, hc3 = st.columns(3)
            hc1.metric("累计盈亏",  f"¥{total_pnl_hist:+.0f}")
            hc2.metric("胜率",      f"{win_rate_hist:.0f}%")
            hc3.metric("交易笔数",  len(df_closed))
            st.dataframe(
                df_closed,
                use_container_width=True, hide_index=True,
                column_config={
                    "盈亏":  st.column_config.NumberColumn(format="¥%.0f"),
                    "盈亏%": st.column_config.NumberColumn(format="%.1f%%"),
                }
            )

    with sub2:
        hist_plans = [p for p in storage.get_trade_plans() if p.get("status") != "DRAFT"]
        if not hist_plans:
            st.info("暂无历史计划记录。")
        else:
            rows2 = []
            for p in hist_plans:
                adv = get_linked_advice(p.get("linked_advice_id"))
                rows2.append({
                    "代码":   p["stock_code"],
                    "名称":   p.get("stock_name", ""),
                    "方向":   p.get("direction", "LONG"),
                    "状态":   CN.status(p.get("status", "")),
                    "入场价": p.get("entry_price"),
                    "止损":   p.get("stop_loss"),
                    "目标1":  p.get("target_1"),
                    "RR":     p.get("rr_ratio"),
                    "建议":   CN.advice(adv.get("advice_type", "—")),
                    "生成时间": str(p.get("created_at", ""))[:16],
                })
            st.dataframe(pd.DataFrame(rows2), use_container_width=True, hide_index=True)
