"""
main.py — WyckoffPro V3.1 主入口
初始化所有模块，提供每日分析 pipeline，启动 Streamlit UI。
"""
from __future__ import annotations
import os
import sys
import time
import yaml
import asyncio
from datetime import datetime
from typing import List, Dict
from loguru import logger
import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv 未安装时直接从系统环境变量读取


# ─── 全局配置加载 ───
def load_config(config_path: str = "config/default.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # 环境变量覆盖 yaml 占位符（优先级：.env / 系统环境变量 > yaml）
    if os.getenv("TUSHARE_TOKEN"):
        cfg["data"]["tushare_token"] = os.getenv("TUSHARE_TOKEN")
    if os.getenv("DEEPSEEK_API_KEY"):
        cfg["ai"]["api_key"] = os.getenv("DEEPSEEK_API_KEY")
    return cfg


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "default.yaml")
config = load_config(CONFIG_PATH)

# ─── 日志配置 ───
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")
logger.add("logs/wyckoffpro_{time:YYYY-MM-DD}.log", rotation="1 day", retention="30 days", level="DEBUG")

# ─── 模块初始化 ───
from data.storage import DataStorage
from data.collector import DataCollector
from data.cleaner import DataCleaner
from engine.thresholds import AdaptiveThresholds
from engine.signal_detector import SignalDetector
from engine.phase_fsm import PhaseFSM
from engine.counter_evidence import CounterEvidenceTracker
from engine.signal_chain import SignalChainTracker
from engine.nine_tests import NineBuyingTests
from engine.supply_demand import SupplyDemandScore
from engine.weis_wave import WeisWave
from engine.channel import ChannelAnalyzer
from engine.pnf_chart import PnFAnalyzer
from engine.mtf_analyzer import MTFAnalyzer
from ai.llm_client import LLMClient
from ai.falsification_engine import FalsificationEngine
from ai.falsification_aggregator import FalsificationAggregator
from ai.falsification_scheduler import FalsificationScheduler
from ai.advisor import AIAdvisor, UserContext, build_quant_scores
from trade.risk_manager import RiskManager
from trade.plan_generator import TradePlanGenerator
from trade.position_tracker import PositionTracker
from data.tushare_hub import TushareHub


# ─── 单例初始化 ───
storage = DataStorage(config["data"].get("db_path", "wyckoffpro.db"))
collector = DataCollector(config["data"], storage)
cleaner = DataCleaner()
adaptive_thresholds = AdaptiveThresholds(config["thresholds"].get("adaptive_lookback", 120))
signal_detector = SignalDetector(config)
phase_fsm = PhaseFSM(config, storage)
counter_tracker = CounterEvidenceTracker(config, storage)
chain_tracker = SignalChainTracker(storage)
nine_tests = NineBuyingTests()
sd_scorer = SupplyDemandScore()
weis = WeisWave()
channel_analyzer = ChannelAnalyzer()
pnf_analyzer = PnFAnalyzer()
mtf_analyzer = MTFAnalyzer()

llm = LLMClient(config)
falsification_engine = FalsificationEngine(llm, config)
falsification_aggregator = FalsificationAggregator()
falsification_scheduler = FalsificationScheduler(config)
advisor = AIAdvisor(llm, config)
risk_mgr = RiskManager(config)
plan_gen = TradePlanGenerator(config, storage, risk_mgr)
position_tracker = PositionTracker(storage)

tushare_hub = TushareHub(
    token=config["data"].get("tushare_token", ""),
    db_path=config["data"].get("db_path", "data/wyckoffpro.db"),
)




async def daily_analysis_pipeline(stock_code: str, timeframe: str = "daily") -> dict:
    """
    每日收盘后对单只股票的完整分析流程。
    """
    start_time = time.time()
    execution_meta = {
        "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "steps": []
    }
    
    logger.info(f"═══ 开始分析 {stock_code} ({timeframe}) ═══")

    # ── L1: 数据获取 ──
    df = storage.get_klines(stock_code, timeframe, 200)
    if df.empty:
        logger.warning(f"{stock_code} 无历史数据，尝试采集...")
        df = await asyncio.to_thread(collector.update_stock, stock_code)
        execution_meta["steps"].append({
            "name": "Data Fetching",
            **collector.last_fetch_metrics
        })
        df = storage.get_klines(stock_code, timeframe, 200)
    else:
        execution_meta["steps"].append({
            "name": "Data Load (Local)",
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "duration": 0.01,
            "source": "SQLite"
        })
    if df.empty:
        return {"error": "无法获取数据"}

    df = cleaner.clean(df)
    thresholds = adaptive_thresholds.calc(df)

    # 构建上下文
    phase_state = phase_fsm.get_current_phase(stock_code, timeframe)
    context = _build_context(df, phase_state, thresholds)

    # ── L1: 信号检测 ──
    signals = signal_detector.scan(df, thresholds, getattr(phase_state, "phase_code", ""), context)
    for sig in signals:
        storage.save_signal({
            "stock_code": stock_code,
            "signal_date": sig.signal_date or df.iloc[-1].get("trade_date", ""),
            "signal_type": sig.signal_type,
            "likelihood": sig.likelihood,
            "strength": sig.strength,
            "phase_code": sig.phase_code,
            "trigger_price": sig.trigger_price,
            "trigger_volume": sig.trigger_volume,
            "rule_detail": sig.rule_detail,
            "timeframe": timeframe,
        })

    # ── L1: 反面证据积分更新 ──
    ce_result = counter_tracker.update(stock_code, df.iloc[-1], context, [s.to_dict() for s in signals])

    # ── L1: 阶段FSM更新 ──
    phase_state = phase_fsm.process_bar(stock_code, df, signals, ce_result, timeframe)

    # ── L1: 信号链更新 ──
    chain = chain_tracker.update(stock_code, signals, getattr(phase_state, "phase_code", ""), timeframe)

    # ── L1: 供需评分 ──
    waves = weis.calculate(df.tail(60))
    weis_balance = weis.analyze_balance(waves)
    channel = channel_analyzer.analyze(df, getattr(phase_state, "tr_upper", 0), getattr(phase_state, "tr_lower", 0))
    context["weis_balance"] = weis_balance
    context["channel_position"] = channel.channel_position
    sd_score = sd_scorer.calculate(df.tail(20))
    sd_breakdown = sd_scorer.get_breakdown(df.tail(20))

    # ── L1: P&F目标价 ──
    pnf_chart = pnf_analyzer.build(df)
    pnf_targets = pnf_analyzer.get_targets(pnf_chart)

    # ── L1: 九大检验 ──
    nine_context = _build_nine_tests_context(df, phase_state, chain, context, thresholds)
    nine_result = nine_tests.evaluate(stock_code, df, nine_context, thresholds)

    # ── L1: MTF分析（简化：仅日线） ──
    mtf_alignment = mtf_analyzer.analyze(
        weekly_phase=getattr(phase_state, "phase_code", "UNKNOWN"),
        weekly_conf=getattr(phase_state, "confidence", 0.5),
        daily_phase=getattr(phase_state, "phase_code", "UNKNOWN"),
        daily_conf=getattr(phase_state, "confidence", 0.5),
    )

    # ── L2-F: 信号证伪（Prompt B）──
    signal_falsifications = {}
    falsi_min_lik = config.get("ai", {}).get("falsification", {}).get("signal_falsify_min_likelihood", 0.50)
    critical_types = set(config.get("ai", {}).get("falsification", {}).get("signal_falsify_critical_types", []))

    for sig in signals:
        should_falsi = (sig.likelihood >= falsi_min_lik or sig.signal_type in critical_types)
        if should_falsi and falsification_scheduler.should_falsify(stock_code, "DAILY"):
            sig_dict = sig.to_dict()
            sig_dict["original_likelihood"] = sig.likelihood
            result = falsification_engine.falsify_signal(stock_code, sig, df, phase_state, context)
            execution_meta["steps"].append({
                "name": f"Signal Falsify ({sig.signal_type})",
                **llm.last_call_metrics
            })
            if result:
                signal_falsifications[sig.signal_type] = {**result, "original_likelihood": sig.likelihood}

    # ── L2-F: 阶段证伪（Prompt A，条件触发）──
    phase_falsification = None
    should_phase_falsi = (
        getattr(phase_state, "duration_days", 0) >= 30 or
        ce_result.get("alert_level") in ("YELLOW", "ORANGE", "RED") or
        falsification_scheduler.should_falsify(stock_code, "DAILY")
    )
    if should_phase_falsi:
        phase_falsification = falsification_engine.falsify_phase(stock_code, phase_state, df, context)
        execution_meta["steps"].append({
            "name": "Phase Falsify",
            **llm.last_call_metrics
        })
        if phase_falsification:
            falsification_scheduler.record(stock_code, phase_falsification.get("falsification_result", ""))

    # ── L2-F: 叙事一致性（Prompt C）──
    narrative_check = falsification_engine.check_narrative(
        stock_code, phase_state, chain, sd_score, sd_breakdown,
        ce_result, mtf_alignment
    )
    execution_meta["steps"].append({
        "name": "Narrative Check (Prompt C)",
        **llm.last_call_metrics
    })

    # ── 聚合证伪结果 ──
    adj = falsification_aggregator.process_results(
        stock_code, phase_falsification, signal_falsifications, narrative_check
    )

    # ── 应用调整 ──
    phase_fsm.adjust_confidence(stock_code, adj["phase_confidence_delta"], timeframe)
    if adj["counter_evidence_delta"] != 0:
        counter_tracker.adjust_score(stock_code, adj["counter_evidence_delta"], "AI", "AI证伪聚合调整")

    # ── 二次紧急反转检查 ──
    final_ce = counter_tracker.get_state(stock_code)
    if final_ce.score >= config.get("emergency_reversal", {}).get("red_reversal_threshold", 71):
        logger.warning(f"[{stock_code}] 🚨 AI证伪后二次触发紧急反转检查，积分={final_ce.score:.1f}")

    # ── L4: 生成投资建议 ──
    qs = build_quant_scores(phase_state, chain, nine_result, sd_score, mtf_alignment, ce_result)
    user_ctx = UserContext()
    pos = position_tracker.get_position(stock_code)
    if pos:
        user_ctx = UserContext(
            holding=True, holding_qty=pos.get("quantity", 0),
            cost_price=pos.get("cost_price", 0),
            current_price=float(df.iloc[-1].get("close", 0))
        )

    advice = advisor.generate_advice(stock_code, qs, adj, user_ctx, channel, pnf_targets)

    # ── 保存建议 ──
    advice_id = storage.save_advice({
        "stock_code": stock_code,
        "advice_type": advice.get("advice_type", "WAIT"),
        "confidence": advice.get("confidence", 0),
        "summary": advice.get("summary", ""),
        "reasoning": advice.get("reasoning", ""),
        "trade_plan": advice.get("trade_plan", {}),
        "key_watch_points": advice.get("key_watch_points", []),
        "invalidation": advice.get("invalidation", ""),
        "valid_until": advice.get("valid_until", ""),
        "quant_score": qs.total,
        "nine_tests_passed": qs.nine_tests_passed,
        "counter_evidence_score": round(ce_result.get("score", 0)),
        "falsification_gate": adj.get("advice_gate", "PASS"),
    })
    advice["id"] = advice_id

    # ── 保存证伪日志 ──
    if phase_falsification or signal_falsifications:
        storage.save_falsification_log({
            "stock_code": stock_code,
            "falsification_type": "DAILY",
            "result": phase_falsification.get("falsification_result", "N/A") if phase_falsification else "NOT_RUN",
            "detail": {
                "phase": phase_falsification,
                "signals": signal_falsifications,
                "narrative": narrative_check,
            },
            "adjustments_applied": adj,
            "token_used": llm.daily_used,
        })

    end_time = time.time()
    execution_meta["end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    execution_meta["total_duration"] = round(end_time - start_time, 2)

    result = {
        "stock_code": stock_code,
        "trade_date": str(df.iloc[-1].get("trade_date", "")),
        "phase": getattr(phase_state, "phase_code", "UNKNOWN"),
        "phase_confidence": getattr(phase_state, "confidence", 0),
        "signals": [s.to_dict() for s in signals],
        "chain_completion": getattr(chain, "completion_pct", 0) if chain else 0,
        "sd_score": sd_score,
        "counter_score": ce_result.get("score", 0),
        "alert_level": ce_result.get("alert_level", "NONE"),
        "nine_tests_passed": nine_result[1] if nine_result else 0,
        "quant_total": qs.total,
        "advice": advice,
        "pnf_targets": pnf_targets,
        "execution_meta": execution_meta,
        "channel": {
            "support_1": channel.support_1,
            "support_2": channel.support_2,
            "resistance_1": channel.resistance_1,
            "cr_upper": channel.upper,
            "cr_lower": channel.lower,
        },
        "alerts": adj.get("alerts", []),
    }

    logger.success(f"===完成分析 {stock_code}: {advice.get('advice_type')} ({advice.get('confidence')}%) ===")
    return result


def _build_context(df, phase_state, thresholds) -> dict:
    """构建分析上下文"""
    ctx = {}
    if df.empty:
        return ctx

    close = df["close"]
    volume = df["volume"]
    ma20 = close.rolling(20, min_periods=5).mean()

    if not ma20.empty and not pd.isna(ma20.iloc[-1]):
        c = float(close.iloc[-1])
        m = float(ma20.iloc[-1])
        ctx["trend"] = "UP" if c > m * 1.02 else ("DOWN" if c < m * 0.98 else "SIDEWAYS")

    ctx["low_60d"] = float(df["low"].tail(60).min())
    ctx["high_60d"] = float(df["high"].tail(60).max())
    ctx["tr_upper"] = getattr(phase_state, "tr_upper", 0)
    ctx["tr_lower"] = getattr(phase_state, "tr_lower", 0)
    ctx["creek_line"] = getattr(phase_state, "creek_line", 0)
    ctx["ice_line"] = getattr(phase_state, "ice_line", 0)
    ctx["phase_code"] = getattr(phase_state, "phase_code", "UNKNOWN")
    ctx["atr_20"] = float(df["atr_20"].iloc[-1]) if "atr_20" in df.columns else 1.0

    # 上涨/下跌波量
    up = df[df["close"] >= df["open"]]
    down = df[df["close"] < df["open"]]
    ctx["up_vol"] = float(up["volume"].tail(20).mean()) if not up.empty else 0
    ctx["down_vol"] = float(down["volume"].tail(20).mean()) if not down.empty else 0
    ctx["vol_reversal"] = ctx["down_vol"] > ctx["up_vol"]

    return ctx


def _build_nine_tests_context(df, phase_state, chain, context, thresholds) -> dict:
    """构建九大买入检验上下文"""
    return {
        "pf_target": 0,  # 简化，实际需要P&F计算
        "has_stopping_sequence": any(
            e.signal_type in ("SC", "AR", "ST") for e in (getattr(chain, "events", []) or [])
        ) if chain else False,
        "up_vol": context.get("up_vol", 1),
        "down_vol": context.get("down_vol", 1),
        "support_tests": 2,  # 简化
        "last_test_vol": float(df["volume"].iloc[-1]) if not df.empty else 0,
        "relative_strength": 1.1,  # 简化，实际需要大盘数据
        "spring_confirmed": any(
            e.signal_type == "Spring" for e in (getattr(chain, "events", []) or [])
        ) if chain else False,
        "shakeout_confirmed": False,
        "downtrend_broken": context.get("trend") in ("UP", "SIDEWAYS"),
        "sos_detected": any(
            e.signal_type == "SOS" for e in (getattr(chain, "events", []) or [])
        ) if chain else False,
        "tr_duration": getattr(phase_state, "duration_days", 0),
    }


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "analyze"
    stocks = [s["stock_code"] for s in storage.get_watchlist()]

    if cmd == "hub-full":
        # 首次全量同步所有数据（耗时较长）
        tushare_hub.full_sync(stocks)

    elif cmd == "hub-daily":
        # 每日收盘后增量同步
        trade_date = sys.argv[2] if len(sys.argv) > 2 else None
        tushare_hub.daily_sync(stocks, trade_date)

    elif cmd == "hub-weekly":
        # 每周末深度同步
        tushare_hub.weekly_sync(stocks)

    elif cmd == "hub-monthly":
        # 每月宏观数据
        tushare_hub.monthly_sync()

    else:
        # 默认：威科夫分析 pipeline
        for s in stocks:
            asyncio.run(daily_analysis_pipeline(s))
