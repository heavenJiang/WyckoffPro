"""
data/cleaner.py — 数据清洗与质量检验
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from loguru import logger


class DataCleaner:
    """K线数据清洗与质量检验"""

    @staticmethod
    def clean(df: pd.DataFrame) -> pd.DataFrame:
        """完整清洗流程"""
        if df.empty:
            return df
        df = df.copy()
        df = DataCleaner._drop_duplicates(df)
        df = DataCleaner._fill_missing(df)
        df = DataCleaner._fix_ohlc(df)
        df = DataCleaner._calc_derived(df)
        df = DataCleaner._remove_outliers(df)
        return df.reset_index(drop=True)

    @staticmethod
    def _drop_duplicates(df: pd.DataFrame) -> pd.DataFrame:
        before = len(df)
        df = df.drop_duplicates(subset=["trade_date"]).sort_values("trade_date").reset_index(drop=True)
        if len(df) < before:
            logger.debug(f"去重：删除 {before - len(df)} 条重复记录")
        return df

    @staticmethod
    def _fill_missing(df: pd.DataFrame) -> pd.DataFrame:
        """填充缺失值：价格用前向填充，成交量用0"""
        price_cols = ["open", "high", "low", "close"]
        df[price_cols] = df[price_cols].ffill().bfill()
        df["volume"] = df["volume"].fillna(0).astype(int)
        df["amount"] = df.get("amount", pd.Series(0, index=df.index)).fillna(0)
        return df

    @staticmethod
    def _fix_ohlc(df: pd.DataFrame) -> pd.DataFrame:
        """修正 OHLC 逻辑错误"""
        df["high"] = df[["open", "high", "low", "close"]].max(axis=1)
        df["low"] = df[["open", "high", "low", "close"]].min(axis=1)
        return df

    @staticmethod
    def _calc_derived(df: pd.DataFrame) -> pd.DataFrame:
        """计算派生字段"""
        prev_close = df["close"].shift(1)
        df["pct_change"] = (df["close"] - prev_close) / prev_close.replace(0, np.nan) * 100
        df["amplitude"] = (df["high"] - df["low"]) / prev_close.replace(0, np.nan)
        df["body_ratio"] = abs(df["close"] - df["open"]) / (df["high"] - df["low"] + 1e-9)
        df["upper_shadow"] = (df["high"] - df[["open", "close"]].max(axis=1)) / (df["high"] - df["low"] + 1e-9)
        df["lower_shadow"] = (df[["open", "close"]].min(axis=1) - df["low"]) / (df["high"] - df["low"] + 1e-9)
        df["is_bullish"] = (df["close"] >= df["open"]).astype(int)

        # ATR-20
        high_low = df["high"] - df["low"]
        high_prev = abs(df["high"] - prev_close)
        low_prev = abs(df["low"] - prev_close)
        tr = pd.concat([high_low, high_prev, low_prev], axis=1).max(axis=1)
        df["atr_20"] = tr.rolling(20, min_periods=1).mean()

        df["pct_change"] = df["pct_change"].fillna(0)
        df["amplitude"] = df["amplitude"].fillna(0)
        return df

    @staticmethod
    def _remove_outliers(df: pd.DataFrame, vol_sigma: float = 5.0) -> pd.DataFrame:
        """标记异常成交量（不删除，只打标签）"""
        if len(df) > 20:
            mean_vol = df["volume"].rolling(20, min_periods=5).mean()
            std_vol = df["volume"].rolling(20, min_periods=5).std()
            df["vol_outlier"] = (df["volume"] > mean_vol + vol_sigma * std_vol).astype(int)
        else:
            df["vol_outlier"] = 0
        return df

    @staticmethod
    def check_quality(df: pd.DataFrame) -> dict:
        """数据质量报告"""
        if df.empty:
            return {"valid": False, "reason": "空数据"}
        report = {
            "total_bars": len(df),
            "missing_close": df["close"].isna().sum(),
            "zero_volume_pct": (df["volume"] == 0).sum() / len(df) * 100,
            "date_range": f"{df['trade_date'].min()} ~ {df['trade_date'].max()}",
        }
        report["valid"] = report["missing_close"] == 0 and report["zero_volume_pct"] < 50
        return report
