"""
engine/signal_chain.py — 信号链追踪
追踪吸筹链（SC→AR→ST→Spring→SOS→JOC）和派发链（BC→AR→UT→SOW→BreakIce）的完成度。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
import json
from loguru import logger


# 吸筹标准链
ACC_CHAIN = ["SC", "AR", "ST", "Spring", "SOS", "JOC"]
ACC_CHAIN_WEIGHTS = {"SC": 20, "AR": 10, "ST": 15, "Spring": 20, "SOS": 20, "JOC": 15}

# 派发标准链
DIS_CHAIN = ["BC", "AR", "UT", "SOW", "BreakIce"]
DIS_CHAIN_WEIGHTS = {"BC": 20, "AR": 10, "UT": 20, "SOW": 25, "BreakIce": 25}


@dataclass
class ChainEvent:
    signal_type: str
    date: str
    likelihood: float
    price: float


@dataclass
class SignalChain:
    stock_code: str
    chain_type: str          # 'ACCUMULATION' or 'DISTRIBUTION'
    start_date: str = ""
    events: List[ChainEvent] = field(default_factory=list)
    completion_pct: int = 0
    status: str = "ACTIVE"  # ACTIVE / COMPLETED / FAILED
    timeframe: str = "daily"


class SignalChainTracker:
    """信号链追踪器"""

    def __init__(self, storage):
        self.storage = storage
        self._chains: Dict[str, SignalChain] = {}

    def update(self, stock_code: str, signals: list, phase_code: str,
               timeframe: str = "daily") -> Optional[SignalChain]:
        """根据新信号更新信号链"""
        chain = self._get_or_create(stock_code, phase_code, timeframe)
        if not chain:
            return None

        for sig in signals:
            sig_type = sig.signal_type if hasattr(sig, "signal_type") else sig.get("signal_type", "")
            sig_date = sig.signal_date if hasattr(sig, "signal_date") else sig.get("signal_date", "")
            sig_likelihood = sig.likelihood if hasattr(sig, "likelihood") else sig.get("likelihood", 0.5)
            sig_price = sig.trigger_price if hasattr(sig, "trigger_price") else sig.get("trigger_price", 0)

            expected = ACC_CHAIN if chain.chain_type == "ACCUMULATION" else DIS_CHAIN
            if sig_type in expected:
                # 避免重复添加（同类型只取最新）
                existing = [e for e in chain.events if e.signal_type == sig_type]
                if not existing or sig_date > existing[-1].date:
                    if existing:
                        chain.events = [e for e in chain.events if e.signal_type != sig_type]
                    chain.events.append(ChainEvent(
                        signal_type=sig_type,
                        date=sig_date,
                        likelihood=sig_likelihood,
                        price=sig_price,
                    ))
                    logger.debug(f"[{stock_code}] 信号链更新: {sig_type} ({sig_likelihood:.2f})")

        chain.completion_pct = self._calc_completion(chain)
        self._save(stock_code, chain)
        return chain

    def get_chain(self, stock_code: str, timeframe: str = "daily") -> Optional[SignalChain]:
        key = f"{stock_code}_{timeframe}"
        return self._chains.get(key)

    def get_completion_pct(self, stock_code: str) -> int:
        chain = self.get_chain(stock_code)
        return chain.completion_pct if chain else 0

    def _get_or_create(self, stock_code: str, phase_code: str, timeframe: str) -> Optional[SignalChain]:
        key = f"{stock_code}_{timeframe}"
        if key in self._chains:
            return self._chains[key]

        # 根据阶段确定链类型
        if "ACC" in phase_code:
            chain_type = "ACCUMULATION"
        elif "DIS" in phase_code:
            chain_type = "DISTRIBUTION"
        else:
            return None  # 不在TR区，不追踪

        chain = SignalChain(
            stock_code=stock_code,
            chain_type=chain_type,
            start_date=datetime.now().date().isoformat(),
            timeframe=timeframe,
        )
        self._chains[key] = chain
        return chain

    def _calc_completion(self, chain: SignalChain) -> int:
        """计算链完成度百分比"""
        weights = ACC_CHAIN_WEIGHTS if chain.chain_type == "ACCUMULATION" else DIS_CHAIN_WEIGHTS
        achieved = sum(
            weights.get(e.signal_type, 0) * min(1.0, e.likelihood * 1.2)
            for e in chain.events
        )
        total = sum(weights.values())
        return min(100, int(achieved / total * 100))

    def _save(self, stock_code: str, chain: SignalChain):
        events_json = json.dumps([
            {"signal_type": e.signal_type, "date": e.date,
             "likelihood": e.likelihood, "price": e.price}
            for e in chain.events
        ], ensure_ascii=False)
        with self.storage._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO signal_chain
                (stock_code, chain_type, start_date, events, completion_pct, status, timeframe)
                VALUES (?,?,?,?,?,?,?)
            """, (stock_code, chain.chain_type, chain.start_date, events_json,
                  chain.completion_pct, chain.status, chain.timeframe))
