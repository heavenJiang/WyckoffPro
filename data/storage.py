"""
data/storage.py — SQLite 读写封装
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
import pandas as pd
from loguru import logger


class DataStorage:
    """SQLite 数据库读写封装"""

    def __init__(self, db_path: str = "wyckoffpro.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self):
        """初始化数据库，执行schema.sql"""
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path, "r", encoding="utf-8") as f:
            sql = f.read()
        with self._get_conn() as conn:
            conn.executescript(sql)
        logger.info(f"Database initialized: {self.db_path}")

    # ─── K线数据 ───
    def save_klines(self, stock_code: str, df: pd.DataFrame, timeframe: str = "daily"):
        """保存K线数据（upsert）"""
        table = f"kline_{timeframe}"
        df = df.copy()
        df["stock_code"] = stock_code
        with self._get_conn() as conn:
            df.to_sql(table, conn, if_exists="append", index=False,
                      method=self._upsert_method(table))
        logger.debug(f"Saved {len(df)} klines for {stock_code} ({timeframe})")

    def get_klines(self, stock_code: str, timeframe: str = "daily",
                   limit: int = 200, start_date: str = None) -> pd.DataFrame:
        """获取K线数据"""
        table = f"kline_{timeframe}"
        with self._get_conn() as conn:
            if start_date:
                sql = f"SELECT * FROM {table} WHERE stock_code=? AND trade_date>=? ORDER BY trade_date"
                df = pd.read_sql(sql, conn, params=(stock_code, start_date))
            else:
                sql = f"SELECT * FROM {table} WHERE stock_code=? ORDER BY trade_date DESC LIMIT ?"
                df = pd.read_sql(sql, conn, params=(stock_code, limit))
                df = df.sort_values("trade_date").reset_index(drop=True)
        return df

    def get_latest_date(self, stock_code: str, timeframe: str = "daily") -> Optional[str]:
        """获取最新数据日期"""
        table = f"kline_{timeframe}"
        with self._get_conn() as conn:
            row = conn.execute(
                f"SELECT MAX(trade_date) as d FROM {table} WHERE stock_code=?",
                (stock_code,)
            ).fetchone()
        return row["d"] if row else None

    # ─── 阶段 ───
    def save_phase(self, stock_code: str, phase_data: dict):
        sql = """
        INSERT OR REPLACE INTO wyckoff_phase
        (stock_code, phase_code, start_date, end_date, confidence, tr_upper, tr_lower,
         ice_line, creek_line, timeframe)
        VALUES (:stock_code,:phase_code,:start_date,:end_date,:confidence,:tr_upper,:tr_lower,
                :ice_line,:creek_line,:timeframe)
        """
        with self._get_conn() as conn:
            conn.execute(sql, {"stock_code": stock_code, **phase_data})

    def get_current_phase(self, stock_code: str, timeframe: str = "daily") -> Optional[Dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM wyckoff_phase WHERE stock_code=? AND timeframe=? AND end_date IS NULL ORDER BY start_date DESC LIMIT 1",
                (stock_code, timeframe)
            ).fetchone()
        return dict(row) if row else None

    def get_phase_history(self, stock_code: str, timeframe: str = "daily") -> List[Dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM wyckoff_phase WHERE stock_code=? AND timeframe=? ORDER BY start_date",
                (stock_code, timeframe)
            ).fetchall()
        return [dict(r) for r in rows]

    # ─── 信号 ───
    def save_signal(self, signal_data: dict):
        sql = """
        INSERT INTO wyckoff_signal
        (stock_code,signal_date,signal_type,likelihood,strength,phase_code,
         trigger_price,trigger_volume,rule_detail,timeframe)
        VALUES (:stock_code,:signal_date,:signal_type,:likelihood,:strength,:phase_code,
                :trigger_price,:trigger_volume,:rule_detail,:timeframe)
        """
        with self._get_conn() as conn:
            conn.execute(sql, signal_data)

    def get_signals(self, stock_code: str, days: int = 60, timeframe: str = "daily") -> List[Dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM wyckoff_signal WHERE stock_code=? AND timeframe=?
                   ORDER BY signal_date DESC LIMIT ?""",
                (stock_code, timeframe, days)
            ).fetchall()
        return [dict(r) for r in rows]

    def update_signal_falsification(self, signal_id: int, result: str, reasoning: str):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE wyckoff_signal SET ai_falsification_result=?, ai_reasoning=? WHERE id=?",
                (result, reasoning, signal_id)
            )

    # ─── 反面证据 ───
    def get_counter_evidence(self, stock_code: str) -> Optional[Dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM counter_evidence WHERE stock_code=? AND is_active=1 ORDER BY id DESC LIMIT 1",
                (stock_code,)
            ).fetchone()
        if row:
            d = dict(row)
            d["events"] = json.loads(d["events"]) if d["events"] else []
            return d
        return None

    def save_counter_evidence(self, stock_code: str, data: dict):
        data["events"] = json.dumps(data.get("events", []), ensure_ascii=False)
        data["last_updated"] = datetime.now().isoformat()
        if data.get("id"):
            sql = """UPDATE counter_evidence SET hypothesis=:hypothesis, current_score=:current_score,
                     alert_level=:alert_level, events=:events, last_updated=:last_updated WHERE id=:id"""
        else:
            data["created_at"] = datetime.now().isoformat()
            sql = """INSERT INTO counter_evidence
                     (stock_code,hypothesis,current_score,alert_level,events,created_at,last_updated)
                     VALUES (:stock_code,:hypothesis,:current_score,:alert_level,:events,:created_at,:last_updated)"""
        with self._get_conn() as conn:
            conn.execute(sql, {"stock_code": stock_code, **data})

    # ─── 证伪记录 ───
    def save_falsification_log(self, record: dict):
        record["executed_at"] = datetime.now().isoformat()
        record["detail"] = json.dumps(record.get("detail", {}), ensure_ascii=False)
        record["adjustments_applied"] = json.dumps(record.get("adjustments_applied", {}), ensure_ascii=False)
        sql = """INSERT INTO falsification_log
                 (stock_code,falsification_type,executed_at,result,detail,adjustments_applied,token_used)
                 VALUES (:stock_code,:falsification_type,:executed_at,:result,:detail,:adjustments_applied,:token_used)"""
        with self._get_conn() as conn:
            conn.execute(sql, record)

    def get_falsification_history(self, stock_code: str, limit: int = 10) -> List[Dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM falsification_log WHERE stock_code=? ORDER BY executed_at DESC LIMIT ?",
                (stock_code, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    # ─── 建议 ───
    def save_advice(self, advice_data: dict) -> int:
        advice_data["created_at"] = datetime.now().isoformat()
        for k in ("trade_plan", "key_watch_points"):
            if isinstance(advice_data.get(k), (dict, list)):
                advice_data[k] = json.dumps(advice_data[k], ensure_ascii=False)
        sql = """INSERT INTO advice
                 (stock_code,created_at,advice_type,confidence,summary,reasoning,trade_plan,
                  key_watch_points,invalidation,valid_until,quant_score,nine_tests_passed,
                  counter_evidence_score,falsification_gate)
                 VALUES (:stock_code,:created_at,:advice_type,:confidence,:summary,:reasoning,
                         :trade_plan,:key_watch_points,:invalidation,:valid_until,:quant_score,
                         :nine_tests_passed,:counter_evidence_score,:falsification_gate)"""
        with self._get_conn() as conn:
            cur = conn.execute(sql, advice_data)
            return cur.lastrowid

    def get_latest_advice(self, stock_code: str) -> Optional[Dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM advice WHERE stock_code=? AND is_expired=0 ORDER BY created_at DESC LIMIT 1",
                (stock_code,)
            ).fetchone()
        if row:
            d = dict(row)
            for k in ("trade_plan", "key_watch_points"):
                if d.get(k):
                    try:
                        d[k] = json.loads(d[k])
                    except Exception:
                        pass
            return d
        return None

    # ─── 交易计划 ───
    def save_trade_plan(self, plan: dict) -> int:
        plan["created_at"] = datetime.now().isoformat()
        sql = """INSERT INTO trade_plan
                 (stock_code,direction,entry_mode,entry_price,stop_loss,target_1,target_2,
                  rr_ratio,position_pct,status,linked_advice_id,created_at,notes)
                 VALUES (:stock_code,:direction,:entry_mode,:entry_price,:stop_loss,:target_1,
                         :target_2,:rr_ratio,:position_pct,:status,:linked_advice_id,:created_at,:notes)"""
        with self._get_conn() as conn:
            cur = conn.execute(sql, plan)
            return cur.lastrowid

    def get_trade_plans(self, stock_code: str = None, status: str = None) -> List[Dict]:
        conditions, params = [], []
        if stock_code:
            conditions.append("stock_code=?")
            params.append(stock_code)
        if status:
            conditions.append("status=?")
            params.append(status)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM trade_plan {where} ORDER BY created_at DESC", params
            ).fetchall()
        return [dict(r) for r in rows]

    # ─── 自选股 ───
    def get_watchlist(self, group: str = None) -> List[Dict]:
        with self._get_conn() as conn:
            if group:
                rows = conn.execute(
                    "SELECT * FROM watchlist WHERE group_name=?", (group,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM watchlist").fetchall()
        return [dict(r) for r in rows]

    def add_to_watchlist(self, stock_code: str, stock_name: str = "", group: str = "default", notes: str = ""):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO watchlist(stock_code,stock_name,group_name,added_at,notes) VALUES(?,?,?,?,?)",
                (stock_code, stock_name, group, datetime.now().date().isoformat(), notes)
            )

    def remove_from_watchlist(self, stock_code: str, group: str = "default"):
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM watchlist WHERE stock_code=? AND group_name=?", (stock_code, group)
            )

    # ─── 持仓 ───
    def get_positions(self) -> List[Dict]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM position WHERE status='OPEN'").fetchall()
        return [dict(r) for r in rows]

    def save_position(self, pos: dict) -> int:
        if pos.get("id"):
            sql = """UPDATE position SET quantity=:quantity,cost_price=:cost_price,
                     current_price=:current_price,status=:status,notes=:notes WHERE id=:id"""
        else:
            pos["open_date"] = datetime.now().date().isoformat()
            sql = """INSERT INTO position(stock_code,stock_name,direction,quantity,cost_price,
                     current_price,open_date,status,notes)
                     VALUES(:stock_code,:stock_name,:direction,:quantity,:cost_price,
                            :current_price,:open_date,:status,:notes)"""
        with self._get_conn() as conn:
            cur = conn.execute(sql, pos)
            return cur.lastrowid

    # ─── 北向资金 ───
    def save_north_flow(self, df: pd.DataFrame):
        with self._get_conn() as conn:
            df.to_sql("north_flow", conn, if_exists="append", index=False,
                      method=self._upsert_method("north_flow"))

    def get_north_flow(self, days: int = 20) -> pd.DataFrame:
        with self._get_conn() as conn:
            df = pd.read_sql(
                "SELECT * FROM north_flow ORDER BY trade_date DESC LIMIT ?",
                conn, params=(days,)
            )
        return df.sort_values("trade_date").reset_index(drop=True)

    # ─── 通用 ───
    @staticmethod
    def _upsert_method(table: str):
        """pandas to_sql method for INSERT OR REPLACE"""
        def method(pd_table, conn, keys, data_iter):
            cols = ", ".join(keys)
            placeholders = ", ".join(["?" for _ in keys])
            sql_str = f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})"
            conn.executemany(sql_str, data_iter)
        return method

    def execute(self, sql: str, params=()) -> List[Dict]:
        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_stock_list(self) -> List[Dict]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM watchlist GROUP BY stock_code").fetchall()
        return [dict(r) for r in rows]
