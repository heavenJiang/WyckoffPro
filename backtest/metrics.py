"""
backtest/metrics.py — 回测绩效指标计算
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass


@dataclass
class BacktestMetrics:
    total_trades: int = 0
    win_trades: int = 0
    lose_trades: int = 0
    win_rate: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    total_return: float = 0.0
    avg_hold_days: float = 0.0


def calc_metrics(trades: list, initial_capital: float = 100000) -> BacktestMetrics:
    """从交易列表计算绩效指标"""
    if not trades:
        return BacktestMetrics()

    m = BacktestMetrics()
    m.total_trades = len(trades)
    wins = [t for t in trades if t.get("pnl_pct", 0) > 0]
    losses = [t for t in trades if t.get("pnl_pct", 0) <= 0]
    m.win_trades = len(wins)
    m.lose_trades = len(losses)
    m.win_rate = round(m.win_trades / m.total_trades * 100, 1)
    m.avg_win_pct = round(np.mean([t["pnl_pct"] for t in wins]) * 100, 1) if wins else 0
    m.avg_loss_pct = round(np.mean([t["pnl_pct"] for t in losses]) * 100, 1) if losses else 0
    total_wins = sum(t.get("pnl_amount", 0) for t in wins)
    total_losses = abs(sum(t.get("pnl_amount", 0) for t in losses))
    m.profit_factor = round(total_wins / total_losses, 2) if total_losses > 0 else float("inf")
    m.avg_hold_days = round(np.mean([t.get("hold_days", 0) for t in trades]), 1)

    # 净值曲线 & 最大回撤
    equity = [initial_capital]
    for t in trades:
        equity.append(equity[-1] + t.get("pnl_amount", 0))
    equity_arr = np.array(equity)
    peak = np.maximum.accumulate(equity_arr)
    drawdown = (equity_arr - peak) / peak
    m.max_drawdown = round(drawdown.min() * 100, 1)
    m.total_return = round((equity[-1] - initial_capital) / initial_capital * 100, 1)

    # 年化收益 & Sharpe
    if len(trades) > 1 and trades[0].get("open_date") and trades[-1].get("close_date"):
        try:
            start = pd.to_datetime(trades[0]["open_date"])
            end = pd.to_datetime(trades[-1]["close_date"])
            years = max((end - start).days / 365, 0.1)
            m.annualized_return = round(((equity[-1]/initial_capital)**(1/years) - 1) * 100, 1)
        except Exception:
            pass

    returns = [t.get("pnl_pct", 0) for t in trades]
    if len(returns) > 1:
        std = np.std(returns)
        mean = np.mean(returns)
        m.sharpe_ratio = round(mean / std * np.sqrt(252), 2) if std > 0 else 0

    return m
