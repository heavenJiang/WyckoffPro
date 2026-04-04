"""
engine/nine_tests.py — 威科夫九大买入/卖出检验
参考文档 4.1 节 + 孟洪涛原书。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class TestResult:
    name: str
    passed: bool
    detail: str = ""


class NineBuyingTests:
    """
    九大买入检验（吸筹阶段成熟度检验）。
    T1-T9 全部通过时，买入时机最佳。
    """

    def evaluate(self, stock_code: str, df, context: dict, thresholds) -> Tuple[Dict[str, TestResult], int]:
        """
        返回 (results_dict, pass_count)
        context 应包含：
            - pf_target: 点数图价格目标
            - has_stopping_sequence: 是否有PS→SC→AR→ST完整序列
            - up_vol: 近20日上涨波量均值
            - down_vol: 近20日下跌波量均值
            - support_tests: 支撑测试次数
            - last_test_vol: 最近测试成交量
            - relative_strength: 个股相对大盘强弱（>1看涨）
            - spring_confirmed: Spring是否已确认
            - shakeout_confirmed: 震仓是否确认
            - downtrend_broken: 下降趋势线是否突破
            - sos_detected: SOS是否出现
            - tr_duration: TR持续天数
        """
        if df is not None and not df.empty:
            close = df["close"].iloc[-1]
            low_recent = df["low"].tail(60).min()
        else:
            close, low_recent = 0, 0

        results = {}

        # T1: 下跌目标已达到
        pf_target = context.get("pf_target", 0)
        t1_passed = pf_target > 0 and close <= pf_target * 1.05 if pf_target else True
        results["T1"] = TestResult("下跌目标已达到（P&F）", t1_passed,
                                   f"P&F目标: {pf_target:.2f}, 当前: {close:.2f}")

        # T2: PS→SC→AR→ST序列完成
        t2_passed = bool(context.get("has_stopping_sequence", False))
        results["T2"] = TestResult("PS→SC→AR→ST序列完成", t2_passed,
                                   "有" if t2_passed else "尚未出现完整停止序列")

        # T3: 看涨量价（反弹放量，回调缩量）
        up_vol = context.get("up_vol", 1)
        down_vol = context.get("down_vol", 1)
        t3_passed = up_vol > down_vol
        results["T3"] = TestResult("看涨量价（反弹放量/回调缩量）", t3_passed,
                                   f"涨波量={up_vol:.0f} vs 跌波量={down_vol:.0f}")

        # T4: 支撑位确立（≥2次测试）
        support_tests = context.get("support_tests", 0)
        t4_passed = support_tests >= 2
        results["T4"] = TestResult("支撑位确立（≥2次测试）", t4_passed,
                                   f"测试次数: {support_tests}")

        # T5: 供应枯竭（低量测试）
        last_test_vol = context.get("last_test_vol", float("inf"))
        low_vol_threshold = getattr(thresholds, "low_vol_threshold", 0) if thresholds else 0
        t5_passed = low_vol_threshold > 0 and last_test_vol < low_vol_threshold
        results["T5"] = TestResult("供应枯竭（低量测试支撑）", t5_passed,
                                   f"测试量={last_test_vol:.0f}, 阈值={low_vol_threshold:.0f}")

        # T6: 个股强于大盘
        rs = context.get("relative_strength", 1.0)
        t6_passed = rs > 1.0
        results["T6"] = TestResult("个股强于大盘（相对强度）", t6_passed,
                                   f"相对强度={rs:.2f}")

        # T7: Spring/震仓已确认
        t7_passed = bool(context.get("spring_confirmed") or context.get("shakeout_confirmed"))
        results["T7"] = TestResult("Spring/震仓已确认", t7_passed,
                                   "已确认" if t7_passed else "未见Spring/震仓")

        # T8: 趋势线突破或SOS出现
        t8_passed = bool(context.get("downtrend_broken") or context.get("sos_detected"))
        results["T8"] = TestResult("下降趋势线突破或SOS出现", t8_passed,
                                   "已突破/SOS" if t8_passed else "趋势线完整/无SOS")

        # T9: 因果充分（TR≥30日）
        tr_duration = context.get("tr_duration", 0)
        t9_passed = tr_duration >= 30
        results["T9"] = TestResult("因果充分（TR≥30交易日）", t9_passed,
                                   f"TR持续: {tr_duration}日")

        passed = sum(1 for r in results.values() if r.passed)
        return results, passed


class NineSellingTests:
    """
    九大卖出检验（派发阶段成熟度检验，对称逻辑）。
    """

    def evaluate(self, stock_code: str, df, context: dict, thresholds) -> Tuple[Dict[str, TestResult], int]:
        if df is not None and not df.empty:
            close = df["close"].iloc[-1]
            high_recent = df["high"].tail(60).max()
        else:
            close, high_recent = 0, 0

        results = {}

        results["T1"] = TestResult("上涨目标已达到", context.get("pf_target_up", False),
                                   f"P&F上涨目标: {context.get('pf_target', 'N/A')}")
        results["T2"] = TestResult("BC→AR→UT→SOW序列完成",
                                   bool(context.get("has_dist_sequence", False)))
        results["T3"] = TestResult("看跌量价（下跌放量/反弹缩量）",
                                   context.get("down_vol", 1) > context.get("up_vol", 1),
                                   f"跌波量={context.get('down_vol',0):.0f} vs 涨波量={context.get('up_vol',0):.0f}")
        results["T4"] = TestResult("阻力位确立（≥2次测试）",
                                   context.get("resistance_tests", 0) >= 2)
        results["T5"] = TestResult("需求枯竭（低量反弹）",
                                   context.get("last_rally_vol", float("inf")) < getattr(thresholds, "low_vol_threshold", float("inf")))
        results["T6"] = TestResult("个股弱于大盘", context.get("relative_strength", 1.0) < 1.0)
        results["T7"] = TestResult("UTAD/UT已确认", bool(context.get("utad_confirmed") or context.get("ut_confirmed")))
        results["T8"] = TestResult("上升趋势线跌破或SOW出现", bool(context.get("uptrend_broken") or context.get("sow_detected")))
        results["T9"] = TestResult("派发原因充分（TR≥30日）", context.get("tr_duration", 0) >= 30)

        passed = sum(1 for r in results.values() if r.passed)
        return results, passed
