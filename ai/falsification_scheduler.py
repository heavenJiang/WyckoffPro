"""
ai/falsification_scheduler.py — 证伪调度器（硬化/冷却机制）
连续3次证伪FAILED → 冷却30交易日（防止浪费Token）。
但 ORANGE_ALERT/用户手动/阶段转换可绕过。
参考文档 2.4.5 节。
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict, List
from loguru import logger


BYPASS_TRIGGERS = {"ORANGE_ALERT", "RED_ALERT", "USER_MANUAL", "PHASE_TRANSITION"}


def _trading_days_since(date_str: str) -> int:
    """估算距某日期的交易日数（简单近似：日历天数*5/7）"""
    try:
        d = datetime.fromisoformat(date_str)
        delta = (datetime.now() - d).days
        return int(delta * 5 / 7)
    except Exception:
        return 999


class FalsificationScheduler:
    """
    证伪调度器。
    跟踪每只股票的历史证伪结果，实现冷却机制。
    """

    def __init__(self, config: dict):
        cfg = config.get("ai", {}).get("falsification", {})
        self.hardening_consecutive = cfg.get("hardening_consecutive", 3)
        self.cooldown_days = cfg.get("hardening_cooldown_days", 30)
        self._history: Dict[str, List[str]] = {}
        self._last_date: Dict[str, str] = {}
        self._cooldown_until: Dict[str, str] = {}

    def should_falsify(self, stock_code: str, trigger_type: str) -> bool:
        """
        判断是否应该执行证伪。
        trigger_type: 'DAILY' / 'ORANGE_ALERT' / 'USER_MANUAL' / 'PHASE_TRANSITION'
        """
        # 绕过触发器始终执行
        if trigger_type in BYPASS_TRIGGERS:
            logger.debug(f"[{stock_code}] 证伪触发器({trigger_type})绕过冷却")
            return True

        # 检查是否在冷却期
        cooldown_until = self._cooldown_until.get(stock_code, "")
        if cooldown_until:
            try:
                until_dt = datetime.fromisoformat(cooldown_until)
                if datetime.now() < until_dt:
                    days_left = (until_dt - datetime.now()).days
                    logger.debug(f"[{stock_code}] 证伪冷却中，还剩{days_left}天")
                    return False
                else:
                    # 冷却期已过
                    del self._cooldown_until[stock_code]
            except Exception:
                pass

        # 检查连续FAILED冷却
        recent = self._history.get(stock_code, [])[-self.hardening_consecutive:]
        if len(recent) == self.hardening_consecutive and all(r == "FAILED" for r in recent):
            last = self._last_date.get(stock_code, "")
            if last and _trading_days_since(last) < self.cooldown_days:
                logger.info(f"[{stock_code}] 连续{self.hardening_consecutive}次证伪FAILED，进入冷却期（{self.cooldown_days}日）")
                # 设置冷却期结束日期
                cooldown_end = (datetime.now() + timedelta(days=self.cooldown_days * 7 // 5)).isoformat()
                self._cooldown_until[stock_code] = cooldown_end
                return False

        return True

    def record(self, stock_code: str, result: str):
        """记录一次证伪结果（FAILED/SUCCEEDED/PARTIAL等）"""
        if stock_code not in self._history:
            self._history[stock_code] = []
        self._history[stock_code].append(result)
        self._last_date[stock_code] = datetime.now().isoformat()
        # 只保留最近10条
        if len(self._history[stock_code]) > 10:
            self._history[stock_code] = self._history[stock_code][-10:]

    def get_history(self, stock_code: str) -> List[str]:
        return self._history.get(stock_code, [])

    def force_reset(self, stock_code: str):
        """手动清除冷却（用于用户强制触发）"""
        self._cooldown_until.pop(stock_code, None)
        self._history.pop(stock_code, None)
        logger.info(f"[{stock_code}] 证伪调度器已重置")

    def get_status(self, stock_code: str) -> dict:
        """获取调度状态"""
        cooldown_until = self._cooldown_until.get(stock_code, "")
        in_cooldown = False
        if cooldown_until:
            try:
                in_cooldown = datetime.now() < datetime.fromisoformat(cooldown_until)
            except Exception:
                pass
        return {
            "in_cooldown": in_cooldown,
            "cooldown_until": cooldown_until,
            "recent_results": self._history.get(stock_code, [])[-5:],
            "last_date": self._last_date.get(stock_code, ""),
        }
