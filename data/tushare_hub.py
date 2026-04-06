"""
data/tushare_hub.py — Tushare 全量数据采集枢纽（V3.1）

覆盖接口：
  基础数据   : stock_basic / etf_basic / opt_basic / st_stocks / hs_const
  低频行情   : daily / weekly / monthly
  财务数据   : income / balancesheet / cashflow / fina_indicator / forecast / dividend
  宏观经济   : cn_gdp / cn_cpi / cn_m
  参考数据   : pledge_stat / share_float / repurchase / stk_holdertrade / top_list / margin
  特色数据   : concept / concept_detail / moneyflow / broker_recommend /
               cyq_perf / stk_factor / report_rc / stk_surv / stk_auction_m

限速策略：10000积分账户，500次/分钟上限 → 安全速率 4次/秒（间隔0.25s）
"""
from __future__ import annotations

import os
import time
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, List, Callable
import pandas as pd
from loguru import logger


# ─── 常量 ───────────────────────────────────────────────────────────────
CALL_INTERVAL = 0.25          # 秒：每次 API 调用后的最小间隔（4次/秒）
BATCH_SLEEP   = 1.0           # 秒：每只股票处理完后的额外冷却
MAX_RETRY     = 3             # 单次接口最大重试次数
RETRY_SLEEP   = 5             # 秒：重试前等待


class RateLimiter:
    """令牌桶限速器：确保 Tushare 调用不超频"""

    def __init__(self, min_interval: float = CALL_INTERVAL):
        self._min_interval = min_interval
        self._last_call = 0.0

    def wait(self):
        elapsed = time.time() - self._last_call
        gap = self._min_interval - elapsed
        if gap > 0:
            time.sleep(gap)
        self._last_call = time.time()


class TushareHub:
    """
    Tushare 全量数据采集枢纽。
    用法：
        hub = TushareHub(token, db_path)
        hub.full_sync(watchlist)    # 首次全量同步（耗时较长）
        hub.daily_sync(watchlist)   # 每日收盘后增量同步
        hub.weekly_sync(watchlist)  # 每周末深度同步
        hub.monthly_sync()          # 每月宏观数据
    """

    def __init__(self, token: str, db_path: str):
        self.db_path = db_path
        self._limiter = RateLimiter()
        self._pro = self._init_tushare(token)
        self._init_schema()

    # ════════════════════════════════════════════════════════════════════
    # 公开入口
    # ════════════════════════════════════════════════════════════════════

    def full_sync(self, watchlist: List[str]):
        """
        首次全量同步。顺序执行：
        基础数据 → 行情 → 参考数据 → 特色数据 → 财务 → 宏观
        预计耗时：watchlist 20只股票约 15～30 分钟
        """
        if self._pro is None:
            logger.error("TushareHub 未初始化（token无效或网络问题），无法执行同步")
            return
        logger.info("═══ TushareHub 全量同步开始 ═══")
        self.sync_stock_basics()
        self.sync_etf_basics()
        self.sync_option_basics()
        self.sync_st_stocks()
        self.sync_hs_const()
        self.sync_macro_all()
        self.sync_concept_all()
        for code in watchlist:
            logger.info(f"─── 全量同步股票 {code} ───")
            ts_code = self._to_ts_code(code)
            self._sync_one_stock_all(ts_code)
            time.sleep(BATCH_SLEEP)
        logger.info("═══ TushareHub 全量同步完成 ═══")

    def daily_sync(self, watchlist: List[str], trade_date: str = None):
        """
        每日收盘后增量同步（快，约 2～5 分钟）。
        包含：日线 / 资金流向 / 龙虎榜 / 融资融券 / 量化因子 / 集合竞价
        """
        if self._pro is None:
            logger.error("TushareHub 未初始化，跳过 daily_sync")
            return
        if not trade_date:
            trade_date = datetime.now().strftime("%Y%m%d")
        logger.info(f"─── 日度同步 {trade_date} ───")
        self._log_task("daily_sync", "DAILY", "ALL", "RUNNING")
        total = 0
        for code in watchlist:
            ts_code = self._to_ts_code(code)
            total += self._safe_save("moneyflow",
                self._fetch_moneyflow(ts_code, trade_date, trade_date))
            total += self._safe_save("stk_factor",
                self._fetch_stk_factor(ts_code, trade_date, trade_date))
            total += self._safe_save("stk_auction",
                self._fetch_stk_auction(ts_code, trade_date, trade_date))
            time.sleep(BATCH_SLEEP)
        total += self._safe_save("top_list", self._fetch_top_list(trade_date))
        total += self._safe_save("margin",   self._fetch_margin_all(trade_date))
        self._log_task("daily_sync", "DAILY", "ALL", "DONE", rows_saved=total)
        logger.info(f"日度同步完成，写入 {total} 条记录")

    def weekly_sync(self, watchlist: List[str]):
        """
        每周末深度同步（中速，约 10～20 分钟）。
        包含：筹码分布 / 盈利预测 / 机构调研 / 解禁 / 增减持 / 回购 / 质押
        """
        if self._pro is None:
            logger.error("TushareHub 未初始化，跳过 weekly_sync")
            return
        logger.info("─── 周度同步 ───")
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        total = 0
        for code in watchlist:
            ts_code = self._to_ts_code(code)
            total += self._safe_save("cyq_perf",    self._fetch_cyq_perf(ts_code))
            total += self._safe_save("report_rc",   self._fetch_report_rc(ts_code))
            total += self._safe_save("stk_surv",    self._fetch_stk_surv(ts_code, start, end))
            total += self._safe_save("share_float", self._fetch_share_float(ts_code))
            total += self._safe_save("holder_trade",self._fetch_holder_trade(ts_code, start, end))
            total += self._safe_save("repurchase",  self._fetch_repurchase(ts_code))
            total += self._safe_save("pledge_stat", self._fetch_pledge_stat(ts_code))
            time.sleep(BATCH_SLEEP)
        total += self._safe_save("broker_recommend", self._fetch_broker_recommend())
        logger.info(f"周度同步完成，写入 {total} 条记录")

    def monthly_sync(self):
        """每月宏观数据 + 财务数据同步"""
        if self._pro is None:
            logger.error("TushareHub 未初始化，跳过 monthly_sync")
            return
        logger.info("─── 月度同步 ───")
        self.sync_macro_all()

    def sync_all_klines_full(self, history_years: int = 5):
        """
        全量A股历史日线（增量：已有数据自动续传）。
        5497只股票 × 2次API调用/只，预计 40～60 分钟。
        """
        if self._pro is None:
            logger.error("TushareHub 未初始化，跳过 kline-full")
            return

        stocks = self._get_all_ts_codes()
        if not stocks:
            logger.error("stock_basic 为空，请先执行 hub-full")
            return

        today = datetime.now().strftime("%Y%m%d")
        cutoff = (datetime.now() - timedelta(days=history_years * 365)).strftime("%Y%m%d")
        logger.info(f"═══ kline-full 开始，共 {len(stocks)} 只，起始 {cutoff} ═══")

        total_rows = 0
        skipped = 0
        for i, ts_code in enumerate(stocks):
            max_date = self._get_kline_max_date(ts_code)
            if max_date and max_date >= today:
                skipped += 1
                continue
            start = max_date if (max_date and max_date > cutoff) else cutoff
            total_rows += self._fetch_and_save_klines(ts_code, start, today)

            if (i + 1) % 100 == 0:
                logger.info(f"kline-full 进度: {i+1}/{len(stocks)}，写入 {total_rows} 条，跳过 {skipped} 只")

        logger.info(f"═══ kline-full 完成：写入 {total_rows} 条，跳过 {skipped} 只 ═══")

    def sync_klines_daily(self, trade_date: str = None):
        """
        单日全市场日线（仅需 2 次 API 调用，覆盖所有A股）。
        每日收盘后增量更新 kline_daily。
        """
        if self._pro is None:
            logger.error("TushareHub 未初始化，跳过 kline-daily")
            return

        if not trade_date:
            trade_date = datetime.now().strftime("%Y%m%d")
        logger.info(f"─── kline-daily {trade_date} ───")

        df_daily = self._call(self._pro.daily, trade_date=trade_date)
        if df_daily is None or df_daily.empty:
            logger.warning(f"kline-daily {trade_date} 无数据（非交易日？）")
            return

        df_basic = self._call(self._pro.daily_basic, trade_date=trade_date,
                              fields="ts_code,trade_date,turnover_rate")
        if df_basic is not None and not df_basic.empty:
            df_daily = df_daily.merge(
                df_basic[["ts_code", "trade_date", "turnover_rate"]],
                on=["ts_code", "trade_date"], how="left"
            )
        else:
            df_daily["turnover_rate"] = None

        rows = self._save_klines_df(df_daily)
        logger.info(f"kline-daily {trade_date} 完成，写入 {rows} 条")

    def sync_stock_basics(self):
        """同步全量A股列表"""
        df = self._call(self._pro.stock_basic,
                        exchange="", list_status="L",
                        fields="ts_code,symbol,name,area,industry,market,list_date,delist_date,is_hs")
        if df is not None and not df.empty:
            df["updated_at"] = datetime.now().isoformat()
            self._upsert(df, "stock_basic")
            logger.info(f"股票列表同步完成：{len(df)} 只")

    def sync_etf_basics(self):
        df = self._call(self._pro.fund_basic, market="E",
                        fields="ts_code,name,fund_type,found_date,market")
        if df is not None and not df.empty:
            df["updated_at"] = datetime.now().isoformat()
            self._upsert(df, "etf_basic")
            logger.info(f"ETF列表同步完成：{len(df)} 只")

    def sync_option_basics(self):
        for exchange in ("SSE", "SZSE"):
            df = self._call(self._pro.opt_basic, exchange=exchange,
                            fields="ts_code,name,underlying_code,call_put,exercise_type,list_date,delist_date")
            if df is not None and not df.empty:
                df["updated_at"] = datetime.now().isoformat()
                self._upsert(df, "option_basic")
        logger.info("期权列表同步完成")

    def sync_st_stocks(self):
        df = self._call(self._pro.namechange,
                        fields="ts_code,name,start_date,end_date,change_reason")
        if df is not None and not df.empty:
            st = df[df["name"].str.contains("ST|退市", na=False)].copy()
            st = st.rename(columns={"change_reason": "updated_at"})
            # 只保留表中列
            st["updated_at"] = datetime.now().isoformat()
            for col in ("ts_code", "name", "start_date", "end_date"):
                if col not in st.columns:
                    st[col] = None
            self._upsert(st[["ts_code", "name", "start_date", "end_date", "updated_at"]], "st_stocks")
            logger.info(f"ST股票同步完成：{len(st)} 只")

    def sync_hs_const(self):
        for hs_type in ("SH", "SZ"):
            df = self._call(self._pro.hs_const, hs_type=hs_type, is_new="1")
            if df is not None and not df.empty:
                df["hs_type"] = hs_type
                df["updated_at"] = datetime.now().isoformat()
                self._upsert(df, "hs_const")
        logger.info("沪深港通成分股同步完成")

    def sync_concept_all(self):
        df = self._call(self._pro.concept, src="ts")
        if df is not None and not df.empty:
            df = df.rename(columns={"code": "concept_code", "name": "concept_name"})
            df["updated_at"] = datetime.now().isoformat()
            self._upsert(df, "concept")
            logger.info(f"概念板块：{len(df)} 个，开始同步成分股...")
            for _, row in df.iterrows():
                try:
                    detail = self._call(self._pro.concept_detail,
                                        id=row["concept_code"], fields="ts_code,name")
                    if detail is not None and not detail.empty:
                        detail["concept_code"] = row["concept_code"]
                        detail["updated_at"] = datetime.now().isoformat()
                        self._upsert(detail, "concept_detail")
                except Exception as e:
                    logger.debug(f"概念成分 {row['concept_code']} 跳过: {e}")
                time.sleep(CALL_INTERVAL)
            logger.info("概念成分股同步完成")

    def sync_macro_all(self):
        """同步三项宏观数据"""
        for fn, table, rename in (
            (self._pro.cn_gdp,  "macro_gdp",   {"quarter": "quarter", "gdp": "gdp", "gdp_yoy": "gdp_yoy",
                                                  "pi": "pi", "si": "si", "ti": "ti"}),
            (self._pro.cn_cpi,  "macro_cpi",   {"month": "month", "nt_val": "nt_val",
                                                  "nt_yoy": "nt_yoy", "nt_mom": "nt_mom"}),
            (self._pro.cn_m,    "macro_money", {"month": "month", "m0": "m0", "m0_yoy": "m0_yoy",
                                                 "m1": "m1", "m1_yoy": "m1_yoy",
                                                 "m2": "m2", "m2_yoy": "m2_yoy"}),
        ):
            df = self._call(fn)
            if df is not None and not df.empty:
                keep = [c for c in rename.keys() if c in df.columns]
                df = df[keep].copy()
                df["updated_at"] = datetime.now().isoformat()
                self._upsert(df, table)
                logger.info(f"宏观数据 [{table}] 同步完成：{len(df)} 条")

    def sync_financial_all(self, ts_code: str):
        """同步单只股票全部财务数据"""
        self._safe_save("financial_income",    self._fetch_income(ts_code))
        self._safe_save("financial_balance",   self._fetch_balance(ts_code))
        self._safe_save("financial_cashflow",  self._fetch_cashflow(ts_code))
        self._safe_save("financial_indicator", self._fetch_fina_indicator(ts_code))
        self._safe_save("forecast",            self._fetch_forecast(ts_code))
        self._safe_save("dividend",            self._fetch_dividend(ts_code))

    # ════════════════════════════════════════════════════════════════════
    # 私有：各接口 fetch 方法
    # ════════════════════════════════════════════════════════════════════

    def _fetch_moneyflow(self, ts_code: str, start: str, end: str) -> Optional[pd.DataFrame]:
        df = self._call(self._pro.moneyflow, ts_code=ts_code,
                        start_date=start, end_date=end)
        if df is None or df.empty:
            return None
        df["updated_at"] = datetime.now().isoformat()
        return df

    def _fetch_stk_factor(self, ts_code: str, start: str, end: str) -> Optional[pd.DataFrame]:
        df = self._call(self._pro.stk_factor, ts_code=ts_code,
                        start_date=start, end_date=end)
        if df is None or df.empty:
            return None
        df["updated_at"] = datetime.now().isoformat()
        return df

    def _fetch_stk_auction(self, ts_code: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """集合竞价：使用 stk_mins 的竞价时段近似（09:15-09:25）"""
        try:
            df = self._call(self._pro.stk_mins, ts_code=ts_code, freq="1min",
                            start_date=start + " 09:14:00",
                            end_date=end + " 09:26:00")
        except Exception:
            return None
        if df is None or df.empty:
            return None
        # 每日取竞价时段最后一条作为开盘集合竞价价格
        df["trade_date"] = pd.to_datetime(df["trade_time"]).dt.strftime("%Y%m%d")
        result = df.groupby("trade_date").agg(
            open_price=("open", "last"),
            open_vol=("vol", "sum"),
            pre_close=("pre_close", "last")
        ).reset_index()
        result["ts_code"] = ts_code
        result["updated_at"] = datetime.now().isoformat()
        return result

    def _fetch_top_list(self, trade_date: str) -> Optional[pd.DataFrame]:
        df = self._call(self._pro.top_list, trade_date=trade_date)
        if df is None or df.empty:
            return None
        df["updated_at"] = datetime.now().isoformat()
        return df

    def _fetch_margin_all(self, trade_date: str) -> Optional[pd.DataFrame]:
        df = self._call(self._pro.margin_detail, trade_date=trade_date)
        if df is None or df.empty:
            return None
        df = df.rename(columns={"ts_code": "ts_code"})
        df["updated_at"] = datetime.now().isoformat()
        return df

    def _fetch_cyq_perf(self, ts_code: str) -> Optional[pd.DataFrame]:
        df = self._call(self._pro.cyq_perf, ts_code=ts_code, limit=10)
        if df is None or df.empty:
            return None
        df["updated_at"] = datetime.now().isoformat()
        return df

    def _fetch_report_rc(self, ts_code: str) -> Optional[pd.DataFrame]:
        df = self._call(self._pro.report_rc, ts_code=ts_code)
        if df is None or df.empty:
            return None
        df["updated_at"] = datetime.now().isoformat()
        return df

    def _fetch_stk_surv(self, ts_code: str, start: str, end: str) -> Optional[pd.DataFrame]:
        df = self._call(self._pro.stk_surv, ts_code=ts_code,
                        start_date=start, end_date=end)
        if df is None or df.empty:
            return None
        df["updated_at"] = datetime.now().isoformat()
        return df

    def _fetch_share_float(self, ts_code: str) -> Optional[pd.DataFrame]:
        df = self._call(self._pro.share_float, ts_code=ts_code)
        if df is None or df.empty:
            return None
        df["updated_at"] = datetime.now().isoformat()
        return df

    def _fetch_holder_trade(self, ts_code: str, start: str, end: str) -> Optional[pd.DataFrame]:
        df = self._call(self._pro.stk_holdertrade, ts_code=ts_code,
                        start_date=start, end_date=end)
        if df is None or df.empty:
            return None
        df["updated_at"] = datetime.now().isoformat()
        return df

    def _fetch_repurchase(self, ts_code: str) -> Optional[pd.DataFrame]:
        df = self._call(self._pro.repurchase, ts_code=ts_code)
        if df is None or df.empty:
            return None
        df["updated_at"] = datetime.now().isoformat()
        return df

    def _fetch_pledge_stat(self, ts_code: str) -> Optional[pd.DataFrame]:
        df = self._call(self._pro.pledge_stat, ts_code=ts_code)
        if df is None or df.empty:
            return None
        df["updated_at"] = datetime.now().isoformat()
        return df

    def _fetch_broker_recommend(self) -> Optional[pd.DataFrame]:
        month = datetime.now().strftime("%Y%m")
        df = self._call(self._pro.broker_recommend, month=month)
        if df is None or df.empty:
            return None
        df["month"] = month
        df["updated_at"] = datetime.now().isoformat()
        return df

    def _fetch_income(self, ts_code: str) -> Optional[pd.DataFrame]:
        df = self._call(self._pro.income, ts_code=ts_code, report_type="1",
                        fields="ts_code,ann_date,end_date,report_type,revenue,n_income,operate_profit,ebit,ebitda")
        if df is None or df.empty:
            return None
        df["updated_at"] = datetime.now().isoformat()
        return df

    def _fetch_balance(self, ts_code: str) -> Optional[pd.DataFrame]:
        df = self._call(self._pro.balancesheet, ts_code=ts_code, report_type="1",
                        fields="ts_code,ann_date,end_date,report_type,total_assets,total_liab,total_hldr_eqy_inc_min_int,money_cap")
        if df is None or df.empty:
            return None
        df["updated_at"] = datetime.now().isoformat()
        return df

    def _fetch_cashflow(self, ts_code: str) -> Optional[pd.DataFrame]:
        df = self._call(self._pro.cashflow, ts_code=ts_code, report_type="1",
                        fields="ts_code,ann_date,end_date,report_type,n_cashflow_act,n_cashflow_inv_act,n_cashflow_fnc_act,free_cashflow")
        if df is None or df.empty:
            return None
        df["updated_at"] = datetime.now().isoformat()
        return df

    def _fetch_fina_indicator(self, ts_code: str) -> Optional[pd.DataFrame]:
        df = self._call(self._pro.fina_indicator, ts_code=ts_code,
                        fields="ts_code,ann_date,end_date,eps,bps,roe,roa,grossprofit_margin,netprofit_margin,debt_to_assets,current_ratio,quick_ratio,pe,pb")
        if df is None or df.empty:
            return None
        df["updated_at"] = datetime.now().isoformat()
        return df

    def _fetch_forecast(self, ts_code: str) -> Optional[pd.DataFrame]:
        df = self._call(self._pro.forecast, ts_code=ts_code)
        if df is None or df.empty:
            return None
        df["updated_at"] = datetime.now().isoformat()
        # 字段对齐
        rename = {"type": "type", "p_change_min": "p_change_min",
                  "p_change_max": "p_change_max", "net_profit_min": "net_profit_min",
                  "net_profit_max": "net_profit_max", "last_parent_net": "last_parent_net",
                  "summary": "summary"}
        keep = ["ts_code", "ann_date", "end_date"] + [c for c in rename if c in df.columns] + ["updated_at"]
        return df[[c for c in keep if c in df.columns]]

    def _fetch_dividend(self, ts_code: str) -> Optional[pd.DataFrame]:
        df = self._call(self._pro.dividend, ts_code=ts_code)
        if df is None or df.empty:
            return None
        df["updated_at"] = datetime.now().isoformat()
        keep = [c for c in ("ts_code", "end_date", "ann_date", "div_proc",
                            "stk_div", "cash_div", "cash_div_tax",
                            "record_date", "ex_date", "pay_date", "updated_at")
                if c in df.columns]
        return df[keep]

    # ════════════════════════════════════════════════════════════════════
    # 内部工具
    # ════════════════════════════════════════════════════════════════════

    def _get_all_ts_codes(self) -> List[str]:
        """从 stock_basic 获取全量 ts_code 列表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute("SELECT ts_code FROM stock_basic").fetchall()
            return [r[0] for r in rows]
        except Exception:
            return []

    def _get_kline_max_date(self, ts_code: str) -> Optional[str]:
        """获取 kline_daily 中该股票最新交易日，统一返回 YYYYMMDD 格式（供 Tushare API 使用）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT MAX(trade_date) FROM kline_daily WHERE stock_code=?",
                    (ts_code,)
                ).fetchone()
            raw = row[0] if row and row[0] else None
            if not raw:
                return None
            # 统一转换为 YYYYMMDD（无论 DB 中存的是 YYYY-MM-DD 还是 YYYYMMDD）
            return pd.to_datetime(str(raw)).strftime("%Y%m%d")
        except Exception:
            return None

    def _fetch_and_save_klines(self, ts_code: str, start: str, end: str) -> int:
        """获取单只股票日线（含换手率）并存入 kline_daily，返回写入行数"""
        df = self._call(self._pro.daily, ts_code=ts_code, start_date=start, end_date=end,
                        fields="ts_code,trade_date,open,high,low,close,pre_close,pct_chg,vol,amount")
        if df is None or df.empty:
            return 0

        df_basic = self._call(self._pro.daily_basic, ts_code=ts_code,
                              start_date=start, end_date=end,
                              fields="ts_code,trade_date,turnover_rate")
        if df_basic is not None and not df_basic.empty:
            df = df.merge(df_basic[["ts_code", "trade_date", "turnover_rate"]],
                          on=["ts_code", "trade_date"], how="left")
        else:
            df["turnover_rate"] = None

        return self._save_klines_df(df)

    def _save_klines_df(self, df: pd.DataFrame) -> int:
        """将 Tushare daily 格式 df 标准化后写入 kline_daily，返回行数"""
        if df is None or df.empty:
            return 0
        df = df.copy()
        df = df.rename(columns={
            "ts_code": "stock_code",
            "vol": "volume",
            "pct_chg": "pct_change",
        })
        # 日期统一转为 YYYY-MM-DD（Tushare 返回 YYYYMMDD）
        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"].astype(str),
                                              format="mixed", errors="coerce").dt.strftime("%Y-%m-%d")
            df = df.dropna(subset=["trade_date"])
        if "pre_close" in df.columns:
            pre = df["pre_close"].replace(0, float("nan"))
            df["amplitude"] = (df["high"] - df["low"]) / pre * 100
            df.drop(columns=["pre_close"], inplace=True, errors="ignore")
        else:
            df["amplitude"] = None
        df["atr_20"] = 0.0  # DataCleaner 运行时按200根K线重新计算
        # 过滤至 schema 列
        keep = ["stock_code", "trade_date", "open", "high", "low", "close",
                "volume", "amount", "turnover_rate", "pct_change", "amplitude", "atr_20"]
        df = df[[c for c in keep if c in df.columns]]
        try:
            self._upsert(df, "kline_daily")
            return len(df)
        except Exception as e:
            logger.warning(f"kline_daily 写入失败: {e}")
            return 0

    def _sync_one_stock_all(self, ts_code: str):
        """对单只股票执行全套同步"""
        self._safe_save("moneyflow",           self._fetch_moneyflow(ts_code, "20200101",
                                                                      datetime.now().strftime("%Y%m%d")))
        self._safe_save("stk_factor",          self._fetch_stk_factor(ts_code, "20200101",
                                                                        datetime.now().strftime("%Y%m%d")))
        self._safe_save("cyq_perf",            self._fetch_cyq_perf(ts_code))
        self._safe_save("pledge_stat",         self._fetch_pledge_stat(ts_code))
        self._safe_save("share_float",         self._fetch_share_float(ts_code))
        self._safe_save("repurchase",          self._fetch_repurchase(ts_code))
        self._safe_save("holder_trade",        self._fetch_holder_trade(
                                                    ts_code, "20200101",
                                                    datetime.now().strftime("%Y%m%d")))
        self._safe_save("stk_surv",            self._fetch_stk_surv(
                                                    ts_code, "20200101",
                                                    datetime.now().strftime("%Y%m%d")))
        self._safe_save("report_rc",           self._fetch_report_rc(ts_code))
        self.sync_financial_all(ts_code)

    def _call(self, fn: Callable, **kwargs) -> Optional[pd.DataFrame]:
        """统一 Tushare 调用：限速 + 自动重试"""
        if self._pro is None:
            return None
        fn_name = getattr(fn, "__name__", None) or getattr(fn, "func", fn).__class__.__name__
        for attempt in range(MAX_RETRY):
            try:
                self._limiter.wait()
                result = fn(**kwargs)
                return result
            except Exception as e:
                msg = str(e)
                if "抱歉" in msg or "权限" in msg or "积分" in msg:
                    logger.warning(f"Tushare 权限/积分不足，跳过 {fn_name}: {e}")
                    return None
                wait = RETRY_SLEEP * (attempt + 1)
                logger.warning(f"Tushare 调用失败（第{attempt+1}次）{fn_name}: {e}，{wait}s后重试")
                time.sleep(wait)
        logger.error(f"Tushare {fn_name} 连续失败，放弃")
        return None

    def _safe_save(self, table: str, df: Optional[pd.DataFrame]) -> int:
        """安全写入：处理列不匹配、空df等异常"""
        if df is None or df.empty:
            return 0
        try:
            self._upsert(df, table)
            return len(df)
        except Exception as e:
            logger.warning(f"写入 [{table}] 失败: {e}")
            return 0

    def _upsert(self, df: pd.DataFrame, table: str):
        """批量 INSERT OR REPLACE"""
        df = df.copy()
        # 只保留 schema 里存在的列，避免多余字段报错
        schema_cols = self._get_table_columns(table)
        if schema_cols:
            df = df[[c for c in df.columns if c in schema_cols]]
        if df.empty:
            return
        with sqlite3.connect(self.db_path) as conn:
            cols = ", ".join(df.columns)
            placeholders = ", ".join(["?" for _ in df.columns])
            sql = f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})"
            conn.executemany(sql, df.itertuples(index=False, name=None))

    def _get_table_columns(self, table: str) -> List[str]:
        """获取表的列名列表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            return [r[1] for r in rows]
        except Exception:
            return []

    def _log_task(self, task_name: str, task_type: str, target: str,
                  status: str, rows_saved: int = 0, error_msg: str = None):
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            if status == "RUNNING":
                conn.execute(
                    """INSERT INTO hub_sync_log
                       (task_name,task_type,target,status,rows_saved,started_at)
                       VALUES(?,?,?,?,?,?)""",
                    (task_name, task_type, target, status, rows_saved, now)
                )
            else:
                conn.execute(
                    """UPDATE hub_sync_log SET status=?, rows_saved=?, finished_at=?, error_msg=?
                       WHERE task_name=? AND target=? AND finished_at IS NULL""",
                    (status, rows_saved, now, error_msg, task_name, target)
                )

    def _init_schema(self):
        """初始化扩展 Schema"""
        schema_path = os.path.join(os.path.dirname(__file__), "schema_ext.sql")
        with open(schema_path, "r", encoding="utf-8") as f:
            sql = f.read()
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(sql)
        logger.debug("TushareHub schema 初始化完成")

    @staticmethod
    def _init_tushare(token: str):
        if not token or token == "YOUR_TUSHARE_TOKEN_HERE":
            logger.warning("Tushare token 未配置，TushareHub 不可用")
            return None
        try:
            import tushare as ts
            pro = ts.pro_api(token)
            # 与 DataCollector 保持一致：通过代理中转
            pro._DataApi__http_url = "http://lianghua.nanyangqiankun.top"
            # 连通性测试
            pro.trade_cal(exchange="SSE", start_date="20240101", end_date="20240102")
            logger.info("TushareHub 连接成功")
            return pro
        except Exception as e:
            logger.error(f"TushareHub 初始化失败: {e}")
            return None

    @staticmethod
    def _to_ts_code(code: str) -> str:
        if "." in code:
            return code.upper()
        num = code.replace("sz", "").replace("sh", "").replace("SZ", "").replace("SH", "")
        return f"{num}.SZ" if num.startswith(("0", "3")) else f"{num}.SH"

    # ════════════════════════════════════════════════════════════════════
    # 便捷查询（供引擎层使用）
    # ════════════════════════════════════════════════════════════════════

    def query(self, sql: str, params=()) -> pd.DataFrame:
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql(sql, conn, params=params)

    def get_moneyflow(self, ts_code: str, days: int = 20) -> pd.DataFrame:
        return self.query(
            "SELECT * FROM moneyflow WHERE ts_code=? ORDER BY trade_date DESC LIMIT ?",
            (ts_code, days)
        )

    def get_cyq_perf(self, ts_code: str) -> pd.DataFrame:
        return self.query(
            "SELECT * FROM cyq_perf WHERE ts_code=? ORDER BY trade_date DESC LIMIT 5",
            (ts_code,)
        )

    def get_financial_indicator(self, ts_code: str, periods: int = 8) -> pd.DataFrame:
        return self.query(
            "SELECT * FROM financial_indicator WHERE ts_code=? ORDER BY end_date DESC LIMIT ?",
            (ts_code, periods)
        )

    def get_pledge_ratio(self, ts_code: str) -> float:
        """最新质押比例%"""
        df = self.query(
            "SELECT pledge_ratio FROM pledge_stat WHERE ts_code=? ORDER BY end_date DESC LIMIT 1",
            (ts_code,)
        )
        return float(df["pledge_ratio"].iloc[0]) if not df.empty else 0.0

    def get_upcoming_float(self, ts_code: str, days_ahead: int = 30) -> pd.DataFrame:
        """未来N天内即将解禁"""
        future = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y%m%d")
        today = datetime.now().strftime("%Y%m%d")
        return self.query(
            "SELECT * FROM share_float WHERE ts_code=? AND float_date BETWEEN ? AND ? ORDER BY float_date",
            (ts_code, today, future)
        )

    def is_st(self, ts_code: str) -> bool:
        """是否当前为ST股"""
        df = self.query(
            "SELECT * FROM st_stocks WHERE ts_code=? AND (end_date IS NULL OR end_date='')",
            (ts_code,)
        )
        return not df.empty

    def get_macro_summary(self) -> dict:
        """最新宏观三指标"""
        result = {}
        for table, pk in (("macro_gdp", "quarter"), ("macro_cpi", "month"), ("macro_money", "month")):
            df = self.query(f"SELECT * FROM {table} ORDER BY {pk} DESC LIMIT 1")
            if not df.empty:
                result[table] = df.iloc[0].to_dict()
        return result
