"""
backtest/engine.py — 回测引擎 V2
基于历史信号的事件驱动回测，评估威科夫策略有效性。

止损类型:
  "atr"   — entry - ATR20 × atr_mult（默认）
  "pct"   — entry × (1 - stop_pct/100)
  "low"   — 近20根K线最低价 × 0.98

目标价:
  固定盈亏比 target_rr 倍风险距离（RR×止损距离）

退出:
  1. 止损触发（当根 low ≤ stop）
  2. 目标触发（当根 high ≥ target）
  3. 主动信号退出（exit_signal_types 信号出现）
  4. 回测结束强制平仓
"""
from __future__ import annotations
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd
from loguru import logger
from backtest.metrics import calc_metrics, BacktestMetrics


class BacktestEngine:
    def __init__(self, config: dict):
        self.config = config
        self.initial_capital = 100_000.0
        self.commission_rate  = 0.0003   # 万三双向
        self.stamp_duty       = 0.001    # 印花税（仅卖出）
        self.position_pct     = 0.30     # 每次使用 30% 资金

    # ──────────────────────────────────────────────────────────────────────
    def run(
        self,
        stock_code: str,
        df: pd.DataFrame,
        signals: List[Dict],
        entry_signal_types: List[str] = None,
        exit_signal_types:  List[str] = None,
        stop_type:    str   = "atr",   # "atr" | "pct" | "low"
        stop_atr_mult: float = 2.0,
        stop_pct:     float  = 5.0,
        target_rr:    float  = 2.0,
        min_likelihood: float = 0.55,
    ) -> dict:
        """
        返回:
          trades        — 交易记录列表
          metrics       — BacktestMetrics 对象
          signal_count  — 有效入场信号数
          equity_curve  — [{"date", "equity", "benchmark"}] 逐日净值
          buy_markers   — [{"date", "price", "signal"}] 买入标记
          sell_markers  — [{"date", "price", "reason"}]  卖出标记
        """
        if entry_signal_types is None:
            entry_signal_types = ["Spring", "JOC", "SOS"]
        if exit_signal_types is None:
            exit_signal_types = []

        # ── 整理入场 / 出场信号索引（同日期取 likelihood 最高）──
        entry_by_date: Dict[str, Dict] = {}
        exit_by_date:  Dict[str, Dict] = {}
        for s in signals:
            stype = s.get("signal_type", "")
            lik   = s.get("likelihood", 0)
            d     = s.get("signal_date", "")
            if not d:
                continue
            if stype in entry_signal_types and lik >= min_likelihood:
                if d not in entry_by_date or lik > entry_by_date[d]["likelihood"]:
                    entry_by_date[d] = s
            if stype in exit_signal_types:
                if d not in exit_by_date or lik > exit_by_date[d]["likelihood"]:
                    exit_by_date[d] = s

        trades: List[Dict]    = []
        buy_markers: List[Dict]  = []
        sell_markers: List[Dict] = []
        equity_curve: List[Dict] = []

        capital  = self.initial_capital
        position: Optional[Dict] = None

        df = df.sort_values("trade_date").reset_index(drop=True)
        first_close = float(df.iloc[0].get("close", 1) or 1)

        for idx, bar in df.iterrows():
            date  = str(bar["trade_date"])
            low   = float(bar.get("low",   0) or 0)
            high  = float(bar.get("high",  0) or 0)
            close = float(bar.get("close", 0) or 0)
            atr20 = float(bar.get("atr_20", 0) or 0)
            if close <= 0:
                continue

            exit_price  = None
            exit_reason = None

            # ── 1. 主动信号退出（优先于止损/目标）──
            if position is not None and date in exit_by_date:
                exit_price  = close
                exit_reason = "SIGNAL"

            # ── 2. 止损 / 目标触发 ──
            if position is not None and exit_price is None:
                if low <= position["stop_loss"]:
                    exit_price  = position["stop_loss"]
                    exit_reason = "STOP_LOSS"
                elif high >= position["target"]:
                    exit_price  = position["target"]
                    exit_reason = "TARGET"

            # ── 3. 平仓结算 ──
            if position is not None and exit_price is not None:
                pnl = (exit_price - position["entry_price"]) * position["shares"]
                pnl -= exit_price * position["shares"] * (self.commission_rate + self.stamp_duty)
                open_dt  = datetime.strptime(position["open_date"], "%Y-%m-%d")
                close_dt = datetime.strptime(date, "%Y-%m-%d")
                trade = {
                    "stock_code":   stock_code,
                    "signal_type":  position["signal_type"],
                    "open_date":    position["open_date"],
                    "close_date":   date,
                    "entry_price":  round(position["entry_price"], 3),
                    "exit_price":   round(exit_price, 3),
                    "stop_loss":    round(position["stop_loss"], 3),
                    "target":       round(position["target"], 3),
                    "shares":       position["shares"],
                    "pnl_amount":   round(pnl, 2),
                    "pnl_pct":      round((exit_price - position["entry_price"]) / position["entry_price"] * 100, 2),
                    "exit_reason":  exit_reason,
                    "hold_days":    (close_dt - open_dt).days,
                }
                trades.append(trade)
                sell_markers.append({"date": date, "price": exit_price, "reason": exit_reason})
                capital  += pnl
                position  = None

            # ── 4. 无持仓时检查入场 ──
            if position is None and date in entry_by_date:
                sig         = entry_by_date[date]
                entry_price = close

                # 计算止损位
                if stop_type == "atr" and atr20 > 0:
                    sl = entry_price - atr20 * stop_atr_mult
                elif stop_type == "pct":
                    sl = entry_price * (1 - stop_pct / 100)
                else:  # "low"
                    recent_low = float(df.iloc[max(0, idx - 20): idx + 1]["low"].min())
                    sl = recent_low * 0.98

                # 止损必须在入场价下方，最大允许 -10%
                sl = min(sl, entry_price * 0.9)
                if sl >= entry_price:
                    sl = entry_price * 0.95

                risk   = entry_price - sl
                target = entry_price + risk * target_rr

                # 仓位计算（整手）
                shares = int(capital * self.position_pct / entry_price / 100) * 100
                if shares <= 0:
                    continue

                # 买入手续费
                buy_fee = entry_price * shares * self.commission_rate
                capital -= buy_fee

                position = {
                    "stock_code":  stock_code,
                    "signal_type": sig.get("signal_type"),
                    "open_date":   date,
                    "entry_price": entry_price,
                    "stop_loss":   round(sl, 3),
                    "target":      round(target, 3),
                    "shares":      shares,
                }
                buy_markers.append({
                    "date":   date,
                    "price":  entry_price,
                    "signal": sig.get("signal_type", ""),
                })

            # ── 5. 逐日净值（含浮盈）──
            if position is not None:
                equity = capital + (close - position["entry_price"]) * position["shares"]
            else:
                equity = capital
            bh_equity = self.initial_capital * (close / first_close)
            equity_curve.append({
                "date":        date,
                "equity":      round(equity, 2),
                "benchmark":   round(bh_equity, 2),
                "in_position": position is not None,
            })

        # ── 6. 回测结束强制平仓 ──
        if position is not None:
            last     = df.iloc[-1]
            ep       = float(last.get("close", position["entry_price"]) or position["entry_price"])
            cd       = str(last["trade_date"])
            pnl      = (ep - position["entry_price"]) * position["shares"]
            pnl     -= ep * position["shares"] * (self.commission_rate + self.stamp_duty)
            open_dt  = datetime.strptime(position["open_date"], "%Y-%m-%d")
            close_dt = datetime.strptime(cd, "%Y-%m-%d")
            trades.append({
                "stock_code":   stock_code,
                "signal_type":  position["signal_type"],
                "open_date":    position["open_date"],
                "close_date":   cd,
                "entry_price":  round(position["entry_price"], 3),
                "exit_price":   round(ep, 3),
                "stop_loss":    round(position["stop_loss"], 3),
                "target":       round(position["target"], 3),
                "shares":       position["shares"],
                "pnl_amount":   round(pnl, 2),
                "pnl_pct":      round((ep - position["entry_price"]) / position["entry_price"] * 100, 2),
                "exit_reason":  "END_OF_DATA",
                "hold_days":    (close_dt - open_dt).days,
            })
            sell_markers.append({"date": cd, "price": ep, "reason": "END_OF_DATA"})

        metrics = calc_metrics(trades, self.initial_capital)
        logger.info(
            f"[{stock_code}] 回测完成: 信号{len(entry_by_date)}个, "
            f"交易{len(trades)}次, 胜率{metrics.win_rate}%, 总收益{metrics.total_return}%"
        )

        return {
            "trades":       trades,
            "metrics":      metrics,
            "signal_count": len(entry_by_date),
            "equity_curve": equity_curve,
            "buy_markers":  buy_markers,
            "sell_markers": sell_markers,
        }
