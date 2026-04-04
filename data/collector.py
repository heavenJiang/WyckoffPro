"""
data/collector.py — 多源数据采集
主数据源：Tushare；备用数据源：AkShare
"""
from __future__ import annotations
import time
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import numpy as np
from loguru import logger


class DataCollector:
    """
    多源K线数据采集。
    优先使用 Tushare；当 Tushare 不可用（未配置token / 接口失败）时，
    自动降级到 AkShare。
    """

    def __init__(self, config: dict, storage):
        self.config = config
        self.storage = storage
        self.tushare_token = config.get("tushare_token", "")
        self._ts_pro = None
        self._ts_available = False
        self._ak_available = False
        self._init_sources()

    def _init_sources(self):
        """初始化数据源"""
        # 尝试初始化 Tushare
        if self.tushare_token:
            try:
                import tushare as ts
                ts.set_token(self.tushare_token)
                self._ts_pro = ts.pro_api()
                # 测试连通性
                self._ts_pro.trade_cal(exchange="SSE", start_date="20240101", end_date="20240102")
                self._ts_available = True
                logger.info("✅ Tushare 初始化成功（主数据源）")
            except Exception as e:
                logger.warning(f"⚠️ Tushare 初始化失败：{e}，将降级到 AkShare")

        # 尝试初始化 AkShare
        try:
            import akshare as ak
            self._ak_available = True
            logger.info("✅ AkShare 可用（备用数据源）")
        except Exception as e:
            logger.warning(f"⚠️ AkShare 不可用：{e}")

        if not self._ts_available and not self._ak_available:
            logger.error("❌ 没有可用的数据源！请检查依赖安装。")

    # ─── 公共接口 ───
    def fetch_klines(self, stock_code: str, timeframe: str = "daily",
                     start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取K线数据并自动选择数据源。
        返回标准化的 DataFrame。
        """
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            years = self.config.get("history_years", 5)
            start_date = (datetime.now() - timedelta(days=years * 365)).strftime("%Y%m%d")

        logger.info(f"采集K线 {stock_code} [{timeframe}] {start_date}~{end_date}")

        df = None
        if self._ts_available:
            try:
                df = self._fetch_tushare(stock_code, timeframe, start_date, end_date)
            except Exception as e:
                logger.warning(f"Tushare 采集失败：{e}，降级到 AkShare")

        if df is None or df.empty:
            if self._ak_available:
                try:
                    df = self._fetch_akshare(stock_code, timeframe, start_date, end_date)
                except Exception as e:
                    logger.error(f"AkShare 采集也失败：{e}")

        if df is None or df.empty:
            logger.warning(f"无法获取 {stock_code} 数据")
            return pd.DataFrame()

        return self._standardize(df, stock_code)

    def update_stock(self, stock_code: str):
        """增量更新某只股票的日K线数据"""
        latest = self.storage.get_latest_date(stock_code, "daily")
        if latest:
            start_date = (datetime.strptime(latest, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
        else:
            years = self.config.get("history_years", 5)
            start_date = (datetime.now() - timedelta(days=years * 365)).strftime("%Y%m%d")

        df = self.fetch_klines(stock_code, "daily", start_date)
        if not df.empty:
            self.storage.save_klines(stock_code, df, "daily")
            logger.info(f"更新 {stock_code} 完成，新增 {len(df)} 条记录")
        return df

    def update_all_watchlist(self):
        """更新所有自选股数据"""
        stocks = self.storage.get_watchlist()
        for s in stocks:
            try:
                self.update_stock(s["stock_code"])
                time.sleep(0.3)  # 防止请求过快
            except Exception as e:
                logger.error(f"更新 {s['stock_code']} 失败：{e}")

    def fetch_stock_info(self, stock_code: str) -> dict:
        """获取股票基础信息"""
        if self._ts_available:
            try:
                return self._fetch_stock_info_tushare(stock_code)
            except Exception as e:
                logger.warning(f"Tushare 获取股票信息失败：{e}")
        if self._ak_available:
            try:
                return self._fetch_stock_info_akshare(stock_code)
            except Exception as e:
                logger.warning(f"AkShare 获取股票信息失败：{e}")
        return {"stock_code": stock_code, "stock_name": stock_code}

    def fetch_north_flow(self, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """获取北向资金数据"""
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

        if self._ts_available:
            try:
                df = self._ts_pro.moneyflow_hsgt(start_date=start_date, end_date=end_date)
                if df is not None and not df.empty:
                    df = df.rename(columns={
                        "trade_date": "trade_date",
                        "north_money": "net_amount",
                        "buy_elg_amount": "buy_amount",
                        "sell_elg_amount": "sell_amount"
                    })
                    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
                    return df[["trade_date", "net_amount", "buy_amount", "sell_amount"]]
            except Exception as e:
                logger.warning(f"北向资金获取失败：{e}")
        return pd.DataFrame()

    # ─── Tushare 私有方法 ───
    def _fetch_tushare(self, stock_code: str, timeframe: str, start_date: str, end_date: str) -> pd.DataFrame:
        ts_code = self._to_tushare_code(stock_code)
        adj = "qfq"  # 前复权

        if timeframe == "daily":
            df = self._ts_pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                return pd.DataFrame()
            # 获取前复权数据
            df_adj = self._ts_pro.adj_factor(ts_code=ts_code, start_date=start_date, end_date=end_date)
            if df_adj is not None and not df_adj.empty:
                df = df.merge(df_adj[["trade_date", "adj_factor"]], on="trade_date", how="left")
                df["adj_factor"] = df["adj_factor"].ffill().fillna(1.0)
                # 应用复权因子
                latest_factor = df["adj_factor"].iloc[0]
                df["open"] = df["open"] * df["adj_factor"] / latest_factor
                df["high"] = df["high"] * df["adj_factor"] / latest_factor
                df["low"] = df["low"] * df["adj_factor"] / latest_factor
                df["close"] = df["close"] * df["adj_factor"] / latest_factor
        elif timeframe == "weekly":
            df = self._ts_pro.weekly(ts_code=ts_code, start_date=start_date, end_date=end_date)
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.sort_values("trade_date").reset_index(drop=True)
        return df

    def _fetch_stock_info_tushare(self, stock_code: str) -> dict:
        ts_code = self._to_tushare_code(stock_code)
        df = self._ts_pro.stock_basic(ts_code=ts_code, fields="ts_code,name,industry,market,list_date")
        if df is not None and not df.empty:
            row = df.iloc[0]
            return {
                "stock_code": stock_code,
                "stock_name": row.get("name", ""),
                "industry": row.get("industry", ""),
                "market": row.get("market", ""),
                "list_date": row.get("list_date", "")
            }
        return {}

    # ─── AkShare 私有方法 ───
    def _fetch_akshare(self, stock_code: str, timeframe: str, start_date: str, end_date: str) -> pd.DataFrame:
        import akshare as ak
        ak_code = self._to_akshare_code(stock_code)
        period_map = {"daily": "daily", "weekly": "weekly"}
        period = period_map.get(timeframe, "daily")

        start_str = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        end_str = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"

        try:
            df = ak.stock_zh_a_hist(
                symbol=ak_code, period=period,
                start_date=start_str, end_date=end_str,
                adjust="qfq"
            )
        except Exception:
            df = ak.stock_zh_a_daily(symbol=f"sz{ak_code}" if ak_code.startswith("0") or ak_code.startswith("3") else f"sh{ak_code}",
                                      start_date=start_str, end_date=end_str, adjust="qfq")

        if df is not None and not df.empty:
            # 标准化列名
            col_map = {
                "日期": "trade_date", "开盘": "open", "最高": "high",
                "最低": "low", "收盘": "close", "成交量": "volume",
                "成交额": "amount", "换手率": "turnover_rate", "涨跌幅": "pct_change",
                "振幅": "amplitude",
                # 英文列名映射
                "date": "trade_date", "Date": "trade_date"
            }
            df = df.rename(columns=col_map)
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
            return df.sort_values("trade_date").reset_index(drop=True)
        return pd.DataFrame()

    def _fetch_stock_info_akshare(self, stock_code: str) -> dict:
        import akshare as ak
        ak_code = self._to_akshare_code(stock_code)
        try:
            df = ak.stock_individual_info_em(symbol=ak_code)
            info = {"stock_code": stock_code}
            for _, row in df.iterrows():
                if "名称" in str(row.iloc[0]) or "股票简称" in str(row.iloc[0]):
                    info["stock_name"] = row.iloc[1]
                if "行业" in str(row.iloc[0]):
                    info["industry"] = row.iloc[1]
            return info
        except Exception:
            return {"stock_code": stock_code}

    # ─── 工具 ───
    @staticmethod
    def _standardize(df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """标准化K线DataFrame"""
        # 确保必要列存在
        required = {"trade_date", "open", "high", "low", "close", "volume"}
        for col in required:
            if col not in df.columns:
                if col == "volume" and "vol" in df.columns:
                    df["volume"] = df["vol"]
                elif col not in df.columns:
                    logger.warning(f"缺少列：{col}")
                    df[col] = np.nan

        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")

        # 计算派生字段
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)
        df["amount"] = pd.to_numeric(df.get("amount", 0), errors="coerce").fillna(0)

        if "pct_change" not in df.columns:
            df["pct_change"] = df["close"].pct_change() * 100
        if "amplitude" not in df.columns:
            df["amplitude"] = (df["high"] - df["low"]) / df["close"].shift(1).replace(0, np.nan)
            df["amplitude"] = df["amplitude"].fillna(0)
        if "turnover_rate" not in df.columns:
            df["turnover_rate"] = 0.0

        # ATR20
        high_low = df["high"] - df["low"]
        high_prev = abs(df["high"] - df["close"].shift(1))
        low_prev = abs(df["low"] - df["close"].shift(1))
        tr = pd.concat([high_low, high_prev, low_prev], axis=1).max(axis=1)
        df["atr_20"] = tr.rolling(20, min_periods=1).mean()

        # 删除全空行
        df = df.dropna(subset=["close"]).reset_index(drop=True)
        return df

    @staticmethod
    def _to_tushare_code(code: str) -> str:
        """转换证券代码为 Tushare 格式（如 000001.SZ）"""
        if "." in code:
            return code.upper()
        code_num = code.replace("sz", "").replace("sh", "").replace("SZ", "").replace("SH", "")
        if code_num.startswith(("0", "3")):
            return f"{code_num}.SZ"
        return f"{code_num}.SH"

    @staticmethod
    def _to_akshare_code(code: str) -> str:
        """转换证券代码为 AkShare 格式（如 000001）"""
        code = code.upper()
        if "." in code:
            return code.split(".")[0]
        return code.replace("SZ", "").replace("SH", "")
