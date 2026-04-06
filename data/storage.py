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
        """初始化数据库，执行 schema.sql + schema_ext.sql"""
        base = os.path.dirname(__file__)
        for schema_file in ("schema.sql", "schema_ext.sql"):
            path = os.path.join(base, schema_file)
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                sql = f.read()
            with self._get_conn() as conn:
                conn.executescript(sql)
        logger.info(f"Database initialized: {self.db_path}")
        self._migrate_date_format()
        self._migrate_schema()

    def _migrate_schema(self):
        """增量添加新列（ALTER TABLE IF NOT EXISTS 的模拟）"""
        migrations = [
            ("analysis_snapshot", "ai_enabled",   "INTEGER DEFAULT 1"),
            ("position",          "stop_loss",     "REAL"),
            ("position",          "target_price",  "REAL"),
            ("position",          "close_price",   "REAL"),
            ("position",          "close_date",    "TEXT"),
            ("position",          "plan_id",       "INTEGER"),
        ]
        with self._get_conn() as conn:
            for table, col, col_def in migrations:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
                    logger.info(f"Schema迁移：{table}.{col} 已添加")
                except Exception:
                    pass  # 列已存在，忽略

    def _migrate_date_format(self):
        """将所有表中 YYYYMMDD 格式日期迁移为 YYYY-MM-DD，并清理重复日期行。
        全程纯 SQL，避免 Python 逐行循环导致的性能问题。
        """
        # (table, date_col, group_by_col_for_dedup)
        # group_by_col: None 表示只需简单 UPDATE（无 UNIQUE 约束），
        #               "stock_code" / "index_code" 表示需要 DELETE+UPDATE
        kline_tables = ["kline_daily", "kline_weekly", "kline_monthly", "kline_hourly"]

        with self._get_conn() as conn:
            # ── 1. kline 表：stock_code + trade_date 构成 PK，需 DELETE+UPDATE ──
            for table in kline_tables:
                try:
                    cnt = conn.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE length(trade_date)=8 AND trade_date NOT LIKE '%-%'"
                    ).fetchone()[0]
                    if not cnt:
                        continue
                    conn.execute(f"""
                        DELETE FROM {table}
                        WHERE length(trade_date)=8 AND trade_date NOT LIKE '%-%'
                          AND EXISTS (
                              SELECT 1 FROM {table} t2
                              WHERE t2.stock_code = {table}.stock_code
                                AND t2.trade_date = printf('%s-%s-%s',
                                        substr({table}.trade_date,1,4),
                                        substr({table}.trade_date,5,2),
                                        substr({table}.trade_date,7,2))
                          )
                    """)
                    deleted = conn.execute("SELECT changes()").fetchone()[0]
                    conn.execute(f"""
                        UPDATE {table}
                        SET trade_date = printf('%s-%s-%s',
                                substr(trade_date,1,4), substr(trade_date,5,2), substr(trade_date,7,2))
                        WHERE length(trade_date)=8 AND trade_date NOT LIKE '%-%'
                    """)
                    updated = conn.execute("SELECT changes()").fetchone()[0]
                    if deleted or updated:
                        logger.info(f"日期迁移：{table} 删除重复 {deleted} 行，更新格式 {updated} 行")
                except Exception as e:
                    logger.warning(f"日期迁移异常 {table}: {e}")

            # ── 2. index_daily：index_code + trade_date 构成 PK ──
            try:
                cnt = conn.execute(
                    "SELECT COUNT(*) FROM index_daily WHERE length(trade_date)=8 AND trade_date NOT LIKE '%-%'"
                ).fetchone()[0]
                if cnt:
                    conn.execute("""
                        DELETE FROM index_daily
                        WHERE length(trade_date)=8 AND trade_date NOT LIKE '%-%'
                          AND EXISTS (
                              SELECT 1 FROM index_daily t2
                              WHERE t2.index_code = index_daily.index_code
                                AND t2.trade_date = printf('%s-%s-%s',
                                        substr(index_daily.trade_date,1,4),
                                        substr(index_daily.trade_date,5,2),
                                        substr(index_daily.trade_date,7,2))
                          )
                    """)
                    deleted = conn.execute("SELECT changes()").fetchone()[0]
                    conn.execute("""
                        UPDATE index_daily
                        SET trade_date = printf('%s-%s-%s',
                                substr(trade_date,1,4), substr(trade_date,5,2), substr(trade_date,7,2))
                        WHERE length(trade_date)=8 AND trade_date NOT LIKE '%-%'
                    """)
                    updated = conn.execute("SELECT changes()").fetchone()[0]
                    if deleted or updated:
                        logger.info(f"日期迁移：index_daily 删除重复 {deleted} 行，更新格式 {updated} 行")
            except Exception as e:
                logger.warning(f"日期迁移异常 index_daily: {e}")

            # ── 3. north_flow：trade_date 是 PK（无 stock_code）──
            try:
                cnt = conn.execute(
                    "SELECT COUNT(*) FROM north_flow WHERE length(trade_date)=8 AND trade_date NOT LIKE '%-%'"
                ).fetchone()[0]
                if cnt:
                    conn.execute("""
                        DELETE FROM north_flow
                        WHERE length(trade_date)=8 AND trade_date NOT LIKE '%-%'
                          AND EXISTS (
                              SELECT 1 FROM north_flow t2
                              WHERE t2.trade_date = printf('%s-%s-%s',
                                        substr(north_flow.trade_date,1,4),
                                        substr(north_flow.trade_date,5,2),
                                        substr(north_flow.trade_date,7,2))
                          )
                    """)
                    deleted = conn.execute("SELECT changes()").fetchone()[0]
                    conn.execute("""
                        UPDATE north_flow
                        SET trade_date = printf('%s-%s-%s',
                                substr(trade_date,1,4), substr(trade_date,5,2), substr(trade_date,7,2))
                        WHERE length(trade_date)=8 AND trade_date NOT LIKE '%-%'
                    """)
                    updated = conn.execute("SELECT changes()").fetchone()[0]
                    if deleted or updated:
                        logger.info(f"日期迁移：north_flow 删除重复 {deleted} 行，更新格式 {updated} 行")
            except Exception as e:
                logger.warning(f"日期迁移异常 north_flow: {e}")

            # ── 4. wyckoff_signal：signal_date 在 UNIQUE 索引中 ──
            try:
                cnt = conn.execute(
                    "SELECT COUNT(*) FROM wyckoff_signal WHERE length(signal_date)=8 AND signal_date NOT LIKE '%-%'"
                ).fetchone()[0]
                if cnt:
                    conn.execute("""
                        DELETE FROM wyckoff_signal
                        WHERE length(signal_date)=8 AND signal_date NOT LIKE '%-%'
                          AND EXISTS (
                              SELECT 1 FROM wyckoff_signal t2
                              WHERE t2.stock_code  = wyckoff_signal.stock_code
                                AND t2.signal_type = wyckoff_signal.signal_type
                                AND t2.timeframe   = wyckoff_signal.timeframe
                                AND t2.signal_date = printf('%s-%s-%s',
                                        substr(wyckoff_signal.signal_date,1,4),
                                        substr(wyckoff_signal.signal_date,5,2),
                                        substr(wyckoff_signal.signal_date,7,2))
                          )
                    """)
                    deleted = conn.execute("SELECT changes()").fetchone()[0]
                    conn.execute("""
                        UPDATE wyckoff_signal
                        SET signal_date = printf('%s-%s-%s',
                                substr(signal_date,1,4), substr(signal_date,5,2), substr(signal_date,7,2))
                        WHERE length(signal_date)=8 AND signal_date NOT LIKE '%-%'
                    """)
                    updated = conn.execute("SELECT changes()").fetchone()[0]
                    if deleted or updated:
                        logger.info(f"日期迁移：wyckoff_signal 删除重复 {deleted} 行，更新格式 {updated} 行")
                # confirm_date 无 UNIQUE 约束，直接 UPDATE
                conn.execute("""
                    UPDATE wyckoff_signal
                    SET confirm_date = printf('%s-%s-%s',
                            substr(confirm_date,1,4), substr(confirm_date,5,2), substr(confirm_date,7,2))
                    WHERE confirm_date IS NOT NULL
                      AND length(confirm_date)=8 AND confirm_date NOT LIKE '%-%'
                """)
            except Exception as e:
                logger.warning(f"日期迁移异常 wyckoff_signal: {e}")

            # ── 5. wyckoff_phase：start_date 在 UNIQUE 约束中 ──
            try:
                cnt = conn.execute(
                    "SELECT COUNT(*) FROM wyckoff_phase WHERE length(start_date)=8 AND start_date NOT LIKE '%-%'"
                ).fetchone()[0]
                if cnt:
                    conn.execute("""
                        DELETE FROM wyckoff_phase
                        WHERE length(start_date)=8 AND start_date NOT LIKE '%-%'
                          AND EXISTS (
                              SELECT 1 FROM wyckoff_phase t2
                              WHERE t2.stock_code = wyckoff_phase.stock_code
                                AND t2.timeframe  = wyckoff_phase.timeframe
                                AND t2.start_date = printf('%s-%s-%s',
                                        substr(wyckoff_phase.start_date,1,4),
                                        substr(wyckoff_phase.start_date,5,2),
                                        substr(wyckoff_phase.start_date,7,2))
                          )
                    """)
                    deleted = conn.execute("SELECT changes()").fetchone()[0]
                    conn.execute("""
                        UPDATE wyckoff_phase
                        SET start_date = printf('%s-%s-%s',
                                substr(start_date,1,4), substr(start_date,5,2), substr(start_date,7,2))
                        WHERE length(start_date)=8 AND start_date NOT LIKE '%-%'
                    """)
                    updated = conn.execute("SELECT changes()").fetchone()[0]
                    if deleted or updated:
                        logger.info(f"日期迁移：wyckoff_phase 删除重复 {deleted} 行，更新格式 {updated} 行")
                # end_date 无 UNIQUE 约束
                conn.execute("""
                    UPDATE wyckoff_phase
                    SET end_date = printf('%s-%s-%s',
                            substr(end_date,1,4), substr(end_date,5,2), substr(end_date,7,2))
                    WHERE end_date IS NOT NULL AND length(end_date)=8 AND end_date NOT LIKE '%-%'
                """)
            except Exception as e:
                logger.warning(f"日期迁移异常 wyckoff_phase: {e}")

            # ── 6. analysis_snapshot.trade_date：无 UNIQUE 约束，直接 UPDATE ──
            try:
                conn.execute("""
                    UPDATE analysis_snapshot
                    SET trade_date = printf('%s-%s-%s',
                            substr(trade_date,1,4), substr(trade_date,5,2), substr(trade_date,7,2))
                    WHERE trade_date IS NOT NULL AND length(trade_date)=8 AND trade_date NOT LIKE '%-%'
                """)
            except Exception as e:
                logger.warning(f"日期迁移异常 analysis_snapshot: {e}")

            # ── 7. signal_chain.start_date：无 UNIQUE 约束，直接 UPDATE ──
            try:
                conn.execute("""
                    UPDATE signal_chain
                    SET start_date = printf('%s-%s-%s',
                            substr(start_date,1,4), substr(start_date,5,2), substr(start_date,7,2))
                    WHERE start_date IS NOT NULL AND length(start_date)=8 AND start_date NOT LIKE '%-%'
                """)
            except Exception as e:
                logger.warning(f"日期迁移异常 signal_chain: {e}")

    @staticmethod
    def _normalize_date_col(df: pd.DataFrame, col: str = "trade_date") -> pd.DataFrame:
        """将 trade_date 列统一为 YYYY-MM-DD 格式（兼容 YYYYMMDD 和带时间的字符串）"""
        if col not in df.columns:
            return df
        df = df.copy()
        df[col] = pd.to_datetime(df[col], format="mixed", errors="coerce").dt.strftime("%Y-%m-%d")
        df = df.dropna(subset=[col])
        return df

    # ─── K线数据 ───
    def save_klines(self, stock_code: str, df: pd.DataFrame, timeframe: str = "daily"):
        """保存K线数据（upsert），写入前统一日期格式为 YYYY-MM-DD"""
        table = f"kline_{timeframe}"
        df = self._normalize_date_col(df.copy())
        df["stock_code"] = stock_code
        with self._get_conn() as conn:
            df.to_sql(table, conn, if_exists="append", index=False,
                      method=self._upsert_method(table))
        logger.debug(f"Saved {len(df)} klines for {stock_code} ({timeframe})")

    def get_klines(self, stock_code: str, timeframe: str = "daily",
                   limit: int = 200, start_date: str = None) -> pd.DataFrame:
        """获取K线数据，读出后统一 trade_date 为 YYYY-MM-DD"""
        table = f"kline_{timeframe}"
        with self._get_conn() as conn:
            # 取该股票所有数据，Python 端再过滤（避免 DB 文本比较 YYYYMMDD vs YYYY-MM-DD 混用）
            # 用 LIMIT 兜底防止极端情况读取过多（单股最多5年×250根≈1250条，可控）
            sql = f"SELECT * FROM {table} WHERE stock_code=? ORDER BY trade_date DESC LIMIT 2000"
            df = pd.read_sql(sql, conn, params=(stock_code,))

        if df.empty:
            return df

        # 统一日期格式
        df = self._normalize_date_col(df)
        df = df.sort_values("trade_date").reset_index(drop=True)

        # 去除可能存在的重复日期（YYYYMMDD 与 YYYY-MM-DD 并存时产生），保留 atr_20 较大的那条
        if "atr_20" in df.columns:
            df = (
                df.sort_values(["trade_date", "atr_20"], ascending=[True, False])
                  .drop_duplicates(subset=["trade_date"], keep="first")
                  .reset_index(drop=True)
            )
        else:
            df = df.drop_duplicates(subset=["trade_date"]).reset_index(drop=True)

        # 按 start_date 过滤（此时日期已是 YYYY-MM-DD，字符串比较安全）
        if start_date:
            try:
                start_norm = pd.to_datetime(str(start_date)).strftime("%Y-%m-%d")
            except Exception:
                start_norm = start_date
            df = df[df["trade_date"] >= start_norm].reset_index(drop=True)
        else:
            df = df.tail(limit).reset_index(drop=True)

        # ATR-20 从 OHLC 重新计算：历史批量导入数据 atr_20 全为 0，DB 存储值不可信
        if "atr_20" in df.columns and not df.empty:
            prev_close = df["close"].shift(1)
            tr = pd.concat([
                df["high"] - df["low"],
                (df["high"] - prev_close).abs(),
                (df["low"]  - prev_close).abs(),
            ], axis=1).max(axis=1)
            df["atr_20"] = tr.rolling(20, min_periods=1).mean()

        return df

    def get_latest_date(self, stock_code: str, timeframe: str = "daily") -> Optional[str]:
        """获取最新数据日期，统一返回 YYYY-MM-DD 格式"""
        table = f"kline_{timeframe}"
        with self._get_conn() as conn:
            row = conn.execute(
                f"SELECT MAX(trade_date) as d FROM {table} WHERE stock_code=?",
                (stock_code,)
            ).fetchone()
        raw = row["d"] if row else None
        if not raw:
            return None
        try:
            return pd.to_datetime(str(raw)).strftime("%Y-%m-%d")
        except Exception:
            return raw

    # ─── 阶段 ───
    def save_phase(self, stock_code: str, phase_data: dict):
        # 归一化日期字段
        phase_data["start_date"] = self._norm_date(phase_data.get("start_date"))
        if phase_data.get("end_date"):
            phase_data["end_date"] = self._norm_date(phase_data["end_date"])
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
    @staticmethod
    def _norm_date(val: Optional[str]) -> Optional[str]:
        """将单个日期字符串统一为 YYYY-MM-DD；None 透传"""
        if not val:
            return val
        try:
            return pd.to_datetime(str(val)).strftime("%Y-%m-%d")
        except Exception:
            return val

    def save_signal(self, signal_data: dict):
        # 归一化日期字段，避免 YYYYMMDD 混入 DB
        signal_data["signal_date"] = self._norm_date(signal_data.get("signal_date"))
        if signal_data.get("confirm_date"):
            signal_data["confirm_date"] = self._norm_date(signal_data["confirm_date"])
        with self._get_conn() as conn:
            # 先尝试更新（同一日期/类型/周期已存在），再插入
            updated = conn.execute("""
                UPDATE wyckoff_signal
                SET likelihood=:likelihood, strength=:strength,
                    phase_code=:phase_code, trigger_price=:trigger_price,
                    trigger_volume=:trigger_volume, rule_detail=:rule_detail
                WHERE stock_code=:stock_code AND signal_date=:signal_date
                  AND signal_type=:signal_type AND timeframe=:timeframe
            """, signal_data).rowcount
            if updated == 0:
                conn.execute("""
                    INSERT INTO wyckoff_signal
                    (stock_code,signal_date,signal_type,likelihood,strength,phase_code,
                     trigger_price,trigger_volume,rule_detail,timeframe)
                    VALUES (:stock_code,:signal_date,:signal_type,:likelihood,:strength,
                            :phase_code,:trigger_price,:trigger_volume,:rule_detail,:timeframe)
                """, signal_data)

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

    def update_trade_plan_status(self, plan_id: int, status: str):
        """更新交易计划状态"""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE trade_plan SET status=? WHERE id=?",
                (status, plan_id)
            )

    def get_trade_plans(self, stock_code: str = None, status: str = None) -> List[Dict]:
        conditions, params = [], []
        if stock_code:
            conditions.append("tp.stock_code=?")
            params.append(stock_code)
        if status:
            conditions.append("tp.status=?")
            params.append(status)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        # 尝试从 watchlist 或 stock_info 获取名称
        sql = f"""
            SELECT tp.*, COALESCE(w.stock_name, si.stock_name, tp.stock_code) as stock_name
            FROM trade_plan tp
            LEFT JOIN watchlist w ON tp.stock_code = w.stock_code
            LEFT JOIN stock_info si ON tp.stock_code = si.stock_code
            {where}
            ORDER BY tp.created_at DESC
        """
        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
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
    def get_positions(self, status: str = "OPEN") -> List[Dict]:
        with self._get_conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM position WHERE status=? ORDER BY open_date DESC",
                    (status,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM position ORDER BY open_date DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def save_position(self, pos: dict) -> int:
        # 确保可选字段有默认值
        for f in ("stop_loss", "target_price", "close_price", "close_date", "plan_id"):
            pos.setdefault(f, None)
        if pos.get("id"):
            sql = """UPDATE position
                     SET quantity=:quantity, cost_price=:cost_price,
                         current_price=:current_price, status=:status, notes=:notes,
                         stop_loss=:stop_loss, target_price=:target_price,
                         close_price=:close_price, close_date=:close_date
                     WHERE id=:id"""
        else:
            pos["open_date"] = pos.get("open_date") or datetime.now().date().isoformat()
            sql = """INSERT INTO position
                     (stock_code, stock_name, direction, quantity, cost_price,
                      current_price, open_date, status, notes,
                      stop_loss, target_price, close_price, close_date, plan_id)
                     VALUES
                     (:stock_code, :stock_name, :direction, :quantity, :cost_price,
                      :current_price, :open_date, :status, :notes,
                      :stop_loss, :target_price, :close_price, :close_date, :plan_id)"""
        with self._get_conn() as conn:
            cur = conn.execute(sql, pos)
            return cur.lastrowid

    def partial_close_position(self, pos_id: int, close_qty: int,
                               close_price: float, note: str = "") -> None:
        """部分平仓：减少持仓数量，记录平仓信息；数量归零时自动关闭"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM position WHERE id=?", (pos_id,)
            ).fetchone()
            if not row:
                return
            pos = dict(row)
            remaining = max(0, pos["quantity"] - close_qty)
            append_note = f"[{datetime.now().date()}] 平仓{close_qty}股@{close_price}"
            if note:
                append_note += f" {note}"
            old_notes = pos.get("notes") or ""
            new_notes = f"{old_notes}\n{append_note}".strip()
            if remaining == 0:
                conn.execute(
                    """UPDATE position SET quantity=0, status='CLOSED',
                       close_price=?, close_date=?, notes=? WHERE id=?""",
                    (close_price, datetime.now().date().isoformat(), new_notes, pos_id)
                )
            else:
                conn.execute(
                    "UPDATE position SET quantity=?, notes=? WHERE id=?",
                    (remaining, new_notes, pos_id)
                )

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

    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        """获取股票基本信息"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM stock_info WHERE stock_code=?", (stock_code,)
            ).fetchone()
        return dict(row) if row else None

    def get_stock_name(self, stock_code: str) -> str:
        """多级尝试获取股票名称：Watchlist -> StockInfo -> StockCode"""
        with self._get_conn() as conn:
            # 尝试自选股映射
            w = conn.execute("SELECT stock_name FROM watchlist WHERE stock_code=?", (stock_code,)).fetchone()
            if w and w["stock_name"]:
                return w["stock_name"]
            
            # 尝试库内信息
            s = conn.execute("SELECT stock_name FROM stock_info WHERE stock_code=?", (stock_code,)).fetchone()
            if s and s["stock_name"]:
                return s["stock_name"]
            
        return stock_code

    # ─── 回测结果 ───
    def save_backtest_result(self, stock_code: str, timeframe: str, entry_signals: List[str], metrics: Dict, trades: List[Dict], stock_name: str = None):
        """保存回测结果历史版本"""
        # 优先使用传入的名称，否则多级查找
        name = stock_name or self.get_stock_name(stock_code)
        
        sql = """
            INSERT INTO backtest_result (
                stock_code, stock_name, run_at, timeframe, 
                entry_signals, metrics, trades
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with self._get_conn() as conn:
            conn.execute(sql, (
                stock_code, name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                timeframe, json.dumps(entry_signals), 
                json.dumps(metrics), json.dumps(trades)
            ))
            
    def get_backtest_history(self, stock_code: str = None) -> List[Dict]:
        """获取回测历史列表"""
        where = "WHERE stock_code = ?" if stock_code else ""
        params = (stock_code,) if stock_code else ()
        
        sql = f"SELECT id, stock_code, stock_name, run_at, timeframe, entry_signals, metrics FROM backtest_result {where} ORDER BY run_at DESC"
        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        
        results = []
        for r in rows:
            d = dict(r)
            d["metrics"] = json.loads(d["metrics"]) if d["metrics"] else {}
            d["entry_signals"] = json.loads(d["entry_signals"]) if d["entry_signals"] else []
            results.append(d)
        return results

    def get_backtest_detail(self, result_id: int) -> Optional[Dict]:
        """获取回测详情（含全部交易）"""
        sql = "SELECT * FROM backtest_result WHERE id = ?"
        with self._get_conn() as conn:
            row = conn.execute(sql, (result_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["metrics"] = json.loads(d["metrics"]) if d["metrics"] else {}
        d["trades"] = json.loads(d["trades"]) if d["trades"] else []
        d["entry_signals"] = json.loads(d["entry_signals"]) if d["entry_signals"] else []
        return d

    # ─── 分析快照 ───
    def save_analysis_snapshot(self, snap: dict) -> int:
        """保存单次 pipeline 运行的完整快照"""
        snap = snap.copy()
        snap["run_at"] = datetime.now().isoformat()
        if snap.get("trade_date"):
            snap["trade_date"] = self._norm_date(snap["trade_date"])
        for key in ("signals_json", "steps_json"):
            if isinstance(snap.get(key), (list, dict)):
                snap[key] = json.dumps(snap[key], ensure_ascii=False)
        sql = """
            INSERT INTO analysis_snapshot
              (stock_code, run_at, timeframe, trade_date,
               phase_code, phase_confidence,
               advice_type, confidence, advice_id,
               quant_total, sd_score, counter_score, alert_level,
               nine_tests_passed, chain_completion,
               signals_json, start_time, total_duration, steps_json, ai_enabled)
            VALUES
              (:stock_code, :run_at, :timeframe, :trade_date,
               :phase_code, :phase_confidence,
               :advice_type, :confidence, :advice_id,
               :quant_total, :sd_score, :counter_score, :alert_level,
               :nine_tests_passed, :chain_completion,
               :signals_json, :start_time, :total_duration, :steps_json, :ai_enabled)
        """
        with self._get_conn() as conn:
            cur = conn.execute(sql, {k: snap.get(k) for k in (
                "stock_code", "run_at", "timeframe", "trade_date",
                "phase_code", "phase_confidence",
                "advice_type", "confidence", "advice_id",
                "quant_total", "sd_score", "counter_score", "alert_level",
                "nine_tests_passed", "chain_completion",
                "signals_json", "start_time", "total_duration", "steps_json", "ai_enabled",
            )})
            return cur.lastrowid

    def get_analysis_snapshots(self, stock_code: str, limit: int = 50,
                               ai_enabled: int = None) -> List[Dict]:
        """获取某只股票的分析快照列表（最新在前）
        ai_enabled: None=全部, 1=AI增强, 0=纯规则
        """
        with self._get_conn() as conn:
            if ai_enabled is not None:
                rows = conn.execute(
                    "SELECT * FROM analysis_snapshot WHERE stock_code=? AND ai_enabled=? "
                    "ORDER BY run_at DESC LIMIT ?",
                    (stock_code, ai_enabled, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM analysis_snapshot WHERE stock_code=? ORDER BY run_at DESC LIMIT ?",
                    (stock_code, limit)
                ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for key in ("signals_json", "steps_json"):
                if d.get(key):
                    try:
                        d[key] = json.loads(d[key])
                    except Exception:
                        pass
            result.append(d)
        return result
