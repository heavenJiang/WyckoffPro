"""
ui/components/translations.py
统一的中文翻译枚举——所有 UI 组件的单一来源。
"""
from __future__ import annotations


class CN:
    """英文代码 → 中文的集中映射（枚举类）"""

    # ── 威科夫阶段 ─────────────────────────────────────────────────────────
    PHASE: dict[str, str] = {
        "ACC-A": "吸筹A段·停止行为",
        "ACC-B": "吸筹B段·建立原因",
        "ACC-C": "吸筹C段·测试弹簧",
        "ACC-D": "吸筹D段·需求主导",
        "ACC-E": "吸筹E段·上涨初段",
        "DIS-A": "派发A段·停止行为",
        "DIS-B": "派发B段·建立供应",
        "DIS-C": "派发C段·UTAD冲顶",
        "DIS-D": "派发D段·弱点明显",
        "MKU":   "上涨趋势",
        "MKD":   "下跌趋势",
        "TR_UNDETERMINED": "震荡区·方向未定",
        "UNKNOWN": "未知/待分析",
    }

    # ── 操作建议 ───────────────────────────────────────────────────────────
    ADVICE: dict[str, str] = {
        "STRONG_BUY":  "强烈买入",
        "BUY":         "买入",
        "WATCH":       "观望持有",
        "HOLD":        "继续持有",
        "WAIT":        "等待机会",
        "REDUCE":      "减仓",
        "SELL":        "卖出",
        "STRONG_SELL": "强烈卖出",
    }

    # 建议背景色 / 文字色
    ADVICE_STYLE: dict[str, tuple[str, str]] = {
        "STRONG_BUY":  ("#00695c", "#a7f3d0"),
        "BUY":         ("#1b5e20", "#bbf7d0"),
        "WATCH":       ("#7c3500", "#fed7aa"),
        "HOLD":        ("#37474f", "#cbd5e1"),
        "WAIT":        ("#1a2332", "#94a3b8"),
        "REDUCE":      ("#7f1d1d", "#fca5a5"),
        "SELL":        ("#7f1d1d", "#fca5a5"),
        "STRONG_SELL": ("#4a0404", "#ff8a80"),
    }

    # ── 反面证据告警等级 ───────────────────────────────────────────────────
    ALERT: dict[str, tuple[str, str]] = {
        "NONE":   ("无异常",  "#22c55e"),
        "GREEN":  ("绿·健康", "#22c55e"),
        "YELLOW": ("黄·关注", "#fbbf24"),
        "ORANGE": ("橙·预警", "#f97316"),
        "RED":    ("红·警戒", "#ef4444"),
    }

    # ── 证伪结论 ───────────────────────────────────────────────────────────
    VERDICT: dict[str, str] = {
        "CONFIRMED":  "✅ 确认有效",
        "FALSIFIED":  "❌ 已被证伪",
        "UNCERTAIN":  "⚠️ 结论存疑",
        "GENUINE":    "✅ AI确认",
        "SUSPECT":    "⚠️ AI可疑",
        "FALSE":      "❌ AI否定",
        "NOT_RUN":    "— 未执行",
    }

    # ── 叙事一致性 ─────────────────────────────────────────────────────────
    NARRATIVE: dict[str, str] = {
        "CONSISTENT":   "✅ 叙事一致",
        "MIXED":        "⚠️ 叙事混乱",
        "INCONSISTENT": "❌ 叙事矛盾",
        "HIGH":         "✅ 高度一致",
        "MEDIUM":       "⚠️ 基本一致",
        "LOW":          "❌ 存在矛盾",
    }

    # ── 门控状态 ───────────────────────────────────────────────────────────
    GATE: dict[str, tuple[str, str]] = {
        "PASS":  ("✅ 通过", "#22c55e"),
        "WARN":  ("⚠️ 警告", "#fbbf24"),
        "BLOCK": ("🚫 拦截", "#ef4444"),
    }

    # ── 威科夫信号类型 ─────────────────────────────────────────────────────
    SIGNAL: dict[str, str] = {
        "SC":     "卖出高潮",
        "AR":     "自动反弹",
        "ST":     "二次测试",
        "Spring": "弹簧/震仓",
        "SOS":    "强势突破",
        "SOW":    "弱点信号",
        "UT":     "向上试探",
        "UTAD":   "末期冲顶",
        "JOC":    "跳出冰点",
        "LPSY":   "最后供应点",
        "VDB":    "低量测试",
        "BC":     "买入高潮",
        "PSY":    "初步供给",
    }

    # ── 建议颜色圆点图标（表格/列表用）──────────────────────────────────────
    ADVICE_ICON: dict[str, str] = {
        "STRONG_BUY": "🟢",
        "BUY":        "🟩",
        "WATCH":      "🟡",
        "HOLD":       "⬜",
        "WAIT":       "⬜",
        "REDUCE":     "🟧",
        "SELL":       "🔴",
        "STRONG_SELL":"🔴",
    }

    # ── 时间周期 ───────────────────────────────────────────────────────────
    TIMEFRAME: dict[str, str] = {
        "daily":   "日线",
        "weekly":  "周线",
        "monthly": "月线",
        "hourly":  "小时线",
    }

    # ── 交易/持仓状态 ──────────────────────────────────────────────────────
    STATUS: dict[str, str] = {
        "WIN":         "盈利",
        "LOSS":        "亏损",
        "STOP_LOSS":   "止损出场",
        "TARGET":      "目标出场",
        "END_OF_DATA": "数据结束",
        "OPEN":        "持仓中",
        "DRAFT":       "待执行",
        "EXECUTED":    "已执行",
        "ACTIVE":      "进行中",
        "COMPLETED":   "已完成",
        "CANCELLED":   "已取消",
    }

    # ── 快捷访问方法 ───────────────────────────────────────────────────────
    @classmethod
    def phase(cls, code: str) -> str:
        return cls.PHASE.get(code or "", code or "未知")

    @classmethod
    def advice(cls, code: str) -> str:
        return cls.ADVICE.get(code or "", code or "—")

    @classmethod
    def advice_style(cls, code: str) -> tuple[str, str]:
        """返回 (背景色, 文字色)"""
        return cls.ADVICE_STYLE.get(code or "", ("#1a2332", "#94a3b8"))

    @classmethod
    def alert(cls, code: str) -> tuple[str, str]:
        """返回 (中文标签, 颜色)"""
        return cls.ALERT.get(code or "", (code or "—", "#9ca3af"))

    @classmethod
    def verdict(cls, code: str) -> str:
        return cls.VERDICT.get(code or "", f"⚠️ {code or '—'}")

    @classmethod
    def narrative(cls, code: str) -> str:
        return cls.NARRATIVE.get(code or "", code or "—")

    @classmethod
    def gate(cls, code: str) -> tuple[str, str]:
        """返回 (中文标签含图标, 颜色)"""
        return cls.GATE.get(code or "", (code or "—", "#9ca3af"))

    @classmethod
    def signal(cls, code: str) -> str:
        return cls.SIGNAL.get(code or "", code or "—")

    @classmethod
    def advice_icon(cls, code: str) -> str:
        return cls.ADVICE_ICON.get(code or "", "⬜")

    @classmethod
    def timeframe(cls, code: str) -> str:
        return cls.TIMEFRAME.get(code or "", code or "—")

    @classmethod
    def status(cls, code: str) -> str:
        return cls.STATUS.get(code or "", code or "—")

    @classmethod
    def advice_badge(cls, atype: str, size: str = "13px") -> str:
        """返回带背景色的建议徽章 HTML"""
        bg, fg = cls.advice_style(atype)
        cn = cls.advice(atype)
        return (
            f'<span style="background:{bg};color:{fg};padding:3px 12px;'
            f'border-radius:5px;font-weight:700;font-size:{size};">{cn}</span>'
        )
