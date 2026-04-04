"""
trade/position_tracker.py — 持仓台账管理
"""
from __future__ import annotations
from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger


class PositionTracker:
    """持仓追踪器"""

    def __init__(self, storage):
        self.storage = storage

    def get_positions(self) -> List[Dict]:
        return self.storage.get_positions()

    def open_position(self, stock_code: str, stock_name: str, quantity: int,
                      cost_price: float, current_price: float = 0) -> Dict:
        pos = {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "direction": "LONG",
            "quantity": quantity,
            "cost_price": cost_price,
            "current_price": current_price or cost_price,
            "status": "OPEN",
            "notes": "",
        }
        pid = self.storage.save_position(pos)
        pos["id"] = pid
        logger.info(f"开仓 {stock_code} x{quantity} @ {cost_price}")
        return pos

    def close_position(self, position_id: int):
        self.storage.save_position({"id": position_id, "status": "CLOSED",
                                    "quantity": 0, "cost_price": 0,
                                    "current_price": 0, "notes": "手动平仓"})

    def update_price(self, stock_code: str, current_price: float):
        positions = [p for p in self.get_positions() if p["stock_code"] == stock_code]
        for pos in positions:
            pos["current_price"] = current_price
            self.storage.save_position(pos)

    def get_summary(self) -> Dict:
        positions = self.get_positions()
        total_cost = sum(p["quantity"] * p["cost_price"] for p in positions)
        total_value = sum(p["quantity"] * (p["current_price"] or p["cost_price"]) for p in positions)
        return {
            "count": len(positions),
            "total_cost": round(total_cost, 2),
            "total_value": round(total_value, 2),
            "total_pnl": round(total_value - total_cost, 2),
            "total_pnl_pct": round((total_value - total_cost) / total_cost * 100, 2) if total_cost > 0 else 0,
        }

    def get_position(self, stock_code: str) -> Optional[Dict]:
        positions = [p for p in self.get_positions() if p["stock_code"] == stock_code]
        return positions[0] if positions else None
