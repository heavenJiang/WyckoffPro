"""
backtest/engine.py — 回测引擎
基于历史信号的事件驱动回测，评估威科夫策略有效性。
"""
from __future__ import annotations
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd
from loguru import logger
from backtest.metrics import calc_metrics, BacktestMetrics


class BacktestEngine:
    """
    简单事件驱动回测引擎。
    - 以历史信号（Spring/JOC等）为入场触发
    - 以止损/目标位为出场条件
    - 不考虑成交量/滑点（简化）
    """

    def __init__(self, config: dict):
        self.config = config
        self.initial_capital = 100000.0
        self.commission_rate = 0.0003  # 万三
        self.stamp_duty = 0.001        # 印花税（卖出）

    def run(self, stock_code: str, df: pd.DataFrame,
            signals: List[Dict], entry_signal_types: List[str] = None) -> dict:
        """
        运行回测。
        df: 完整K线数据
        signals: 历史信号列表（来自DB）
        entry_signal_types: 用于入场的信号类型（默认 Spring/JOC）
        """
        if entry_signal_types is None:
            entry_signal_types = ["Spring", "JOC", "SOS"]

        entry_signals = [s for s in signals
                         if s.get("signal_type") in entry_signal_types
                         and s.get("likelihood", 0) >= 0.6]

        trades = []
        capital = self.initial_capital
        position = None

        df = df.sort_values("trade_date").reset_index(drop=True)
        df_dict = {row["trade_date"]: row for _, row in df.iterrows()}

        for sig in sorted(entry_signals, key=lambda s: s.get("signal_date", "")):
            sig_date = sig.get("signal_date", "")
            if sig_date not in df_dict:
                continue
            trigger_bar = df_dict[sig_date]

            if position:
                # 检查是否需要平仓（简化：先处理已有持仓）
                continue

            entry_price = float(trigger_bar.get("close", 0))
            if entry_price <= 0:
                continue

            # 止损：近期低点下方2%
            sig_idx = df[df["trade_date"] == sig_date].index
            if len(sig_idx) == 0:
                continue
            idx = sig_idx[0]
            recent_low = df.iloc[max(0, idx-20):idx+1]["low"].min()
            stop_loss = recent_low * 0.98

            # 仓位
            shares = int(capital * 0.3 / entry_price / 100) * 100
            if shares <= 0:
                continue

            entry_cost = shares * entry_price * (1 + self.commission_rate)
            position = {
                "stock_code": stock_code,
                "signal_type": sig.get("signal_type"),
                "open_date": sig_date,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "target": entry_price * 1.15,  # 默认目标15%
                "shares": shares,
                "entry_cost": entry_cost,
            }

        # 模拟持仓演变（简化逻辑）
        if position:
            # 找到入场后的所有K线，检查止损/目标
            open_idx = df[df["trade_date"] == position["open_date"]].index
            if len(open_idx) > 0:
                future_bars = df.iloc[open_idx[0]+1:]
                for _, bar in future_bars.iterrows():
                    low = float(bar.get("low", 0))
                    high = float(bar.get("high", 0))
                    close = float(bar.get("close", 0))

                    if low <= position["stop_loss"]:
                        # 止损出场
                        exit_price = position["stop_loss"]
                        pnl_amount = (exit_price - position["entry_price"]) * position["shares"]
                        pnl_amount -= exit_price * position["shares"] * (self.commission_rate + self.stamp_duty)
                        open_dt = datetime.strptime(position["open_date"], "%Y-%m-%d")
                        close_dt = datetime.strptime(str(bar["trade_date"]), "%Y-%m-%d")
                        trades.append({
                            "stock_code": stock_code,
                            "open_date": position["open_date"],
                            "close_date": str(bar["trade_date"]),
                            "entry_price": position["entry_price"],
                            "exit_price": exit_price,
                            "shares": position["shares"],
                            "pnl_amount": pnl_amount,
                            "pnl_pct": (exit_price - position["entry_price"]) / position["entry_price"],
                            "exit_reason": "STOP_LOSS",
                            "hold_days": (close_dt - open_dt).days,
                        })
                        position = None
                        break
                    elif high >= position["target"]:
                        # 目标出场
                        exit_price = position["target"]
                        pnl_amount = (exit_price - position["entry_price"]) * position["shares"]
                        pnl_amount -= exit_price * position["shares"] * (self.commission_rate + self.stamp_duty)
                        open_dt = datetime.strptime(position["open_date"], "%Y-%m-%d")
                        close_dt = datetime.strptime(str(bar["trade_date"]), "%Y-%m-%d")
                        trades.append({
                            "stock_code": stock_code,
                            "open_date": position["open_date"],
                            "close_date": str(bar["trade_date"]),
                            "entry_price": position["entry_price"],
                            "exit_price": exit_price,
                            "shares": position["shares"],
                            "pnl_amount": pnl_amount,
                            "pnl_pct": (exit_price - position["entry_price"]) / position["entry_price"],
                            "exit_reason": "TARGET",
                            "hold_days": (close_dt - open_dt).days,
                        })
                        position = None
                        break

        metrics = calc_metrics(trades, self.initial_capital)
        logger.info(f"[{stock_code}] 回测完成: 交易{len(trades)}次, 胜率{metrics.win_rate}%, 总收益{metrics.total_return}%")

        return {
            "trades": trades,
            "metrics": metrics,
            "signal_count": len(entry_signals),
        }
