"""
backtest/optimizer.py — 参数优化（网格搜索）
"""
from __future__ import annotations
from typing import Dict, List, Tuple
from itertools import product
from loguru import logger


class BacktestOptimizer:
    """网格搜索参数优化"""

    def run(self, backtest_engine, stock_code: str, df, signals: List[Dict],
            param_grid: dict = None) -> List[dict]:
        """
        网格搜索最优参数。
        param_grid: {'like_threshold': [0.5, 0.6, 0.7], 'target_pct': [0.1, 0.15, 0.2]}
        """
        if param_grid is None:
            param_grid = {
                "like_threshold": [0.5, 0.6, 0.7],
                "target_pct": [0.10, 0.15, 0.20],
                "stop_pct": [0.03, 0.05, 0.07],
            }

        results = []
        keys = list(param_grid.keys())
        for combo in product(*param_grid.values()):
            params = dict(zip(keys, combo))
            # 调整信号过滤
            filtered = [s for s in signals if s.get("likelihood", 0) >= params.get("like_threshold", 0.6)]
            result = backtest_engine.run(stock_code, df, filtered)
            metrics = result.get("metrics")
            if metrics:
                results.append({
                    "params": params,
                    "win_rate": metrics.win_rate,
                    "profit_factor": metrics.profit_factor,
                    "max_drawdown": metrics.max_drawdown,
                    "total_return": metrics.total_return,
                    "sharpe_ratio": metrics.sharpe_ratio,
                    "score": metrics.profit_factor * metrics.win_rate / max(abs(metrics.max_drawdown), 1),
                })

        results.sort(key=lambda r: r["score"], reverse=True)
        logger.info(f"参数优化完成，共{len(results)}组，最优: {results[0] if results else 'N/A'}")
        return results
