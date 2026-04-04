# WyckoffPro 开发指导文档（V3.0 终稿）

> **文档性质**：可直接交给AI（Claude/Cursor/Copilot）进行代码生成的开发指导书  
> **理论基础**：孟洪涛《威科夫操盘法》+《新威科夫操盘法》完整体系  
> **系统定位**：个人自用本地交易分析工具，生成投资建议，不自动下单  
> **日期**：2026-04-04

---

## 第一部分：策略有效性审查与修正

### 1.1 V2.0策略存在的核心问题

经过逐条审查V2.0 PRD中的策略规则，发现以下关键问题：

| 问题编号 | 问题描述 | 严重程度 | 根因 |
|---------|---------|---------|------|
| S01 | **固定阈值不适应不同股票特性**：SC的量能阈值固定为2.5倍均量，但小盘股日常波动就可能达到3倍，大盘蓝筹可能1.8倍就是异常 | 高 | 一刀切的参数设计 |
| S02 | **信号判定是二值的（是/否）而非概率性的**：现实中大多数市场行为处于模糊地带，不是标准教科书形态 | 高 | 未引入似然度/概率模型 |
| S03 | **缺少威科夫「九大买入检验」和「九大卖出检验」**：这是威科夫五步法Step4的核心工具，书中明确要求通过九项检验综合判定 | 高 | 遗漏 |
| S04 | **未引入维斯波（Weis Wave）**：David Weis基于威科夫发展的波量图是现代威科夫分析的标准工具 | 中 | 遗漏 |
| S05 | **目标价只有P&F计数法一种**：缺少趋势通道投影法、前高前低法等辅助目标位 | 中 | 不完整 |
| S06 | **供需评分（-100到+100）缺少具体计算公式** | 中 | V2.0只声明了维度但没给权重 |
| S07 | **AI能力完全缺失**：未考虑用LLM进行市场叙事分析、模糊信号判读、多源信息综合 | 高 | V2.0无AI设计 |

### 1.2 修正方案总览

| 修正 | 方案 |
|------|------|
| S01 → **自适应阈值** | 每只股票基于自身历史数据计算动态阈值（百分位数法） |
| S02 → **概率云/似然度模型** | 每根K线计算各信号的似然度分数（0-1），取概率坍缩后的最大似然信号 |
| S03 → **九大检验清单** | 实现完整的9-point买入检验和9-point卖出检验自动评分 |
| S04 → **维斯波模块** | 波量聚合+波量对比分析 |
| S05 → **多目标位融合** | P&F + 通道投影 + 前高前低，取交集区域作为目标区间 |
| S06 → **明确的供需评分公式** | 6维度加权评分，公式见下文 |
| S07 → **LLM深度融合** | 4层AI能力嵌入（见第二部分） |

---

## 第二部分：AI/大模型融合架构

### 2.1 AI融合的核心理念

威科夫分析的最大挑战是**主观性**——同一段走势，不同水平的交易者会得出不同结论。民生证券的量化研究也指出这个问题。大模型的价值恰恰在于处理这种**模糊性推理**：

- 规则引擎处理**结构化的量价数据**（精确但僵硬）
- 大模型处理**非结构化的语境判断**（灵活但需要约束）
- 两者融合 = 有纪律的灵活性

### 2.2 四层AI能力架构

```
┌─────────────────────────────────────────────────┐
│  L4: AI投资建议生成器（最终输出层）                │
│  输入：L1-L3全部结果 + 用户持仓上下文              │
│  输出：自然语言投资建议 + 结构化交易计划            │
├─────────────────────────────────────────────────┤
│  L3: AI市场叙事引擎（综合推理层）                  │
│  能力：多源信息综合（技术面+资金面+消息面）         │
│  输入：M2阶段 + M3信号 + 新闻摘要 + 北向资金       │
│  输出：当前市场叙事（谁在做什么，为什么）           │
├─────────────────────────────────────────────────┤
│  L2: AI模糊信号判读器（辅助判定层）                │
│  能力：处理非标准形态、边界情况、信号冲突           │
│  输入：规则引擎的似然度向量 + K线图截图             │
│  输出：修正后的信号判定 + 置信度 + 推理链           │
├─────────────────────────────────────────────────┤
│  L1: 规则引擎 + ML模型（基础计算层）               │
│  能力：确定性的量价计算、阈值判定、特征提取         │
│  纯Python/NumPy，不依赖LLM                        │
└─────────────────────────────────────────────────┘
```

### 2.3 各层详细设计

#### L1: 规则引擎 + ML（基础层，无LLM依赖）

这一层是系统的「骨架」，即使LLM不可用也能独立运行。

```python
# 伪代码：自适应阈值计算
class AdaptiveThresholds:
    """
    每只股票基于自身历史数据动态计算阈值。
    替代V2.0的固定倍数阈值。
    """
    def __init__(self, lookback=120):
        self.lookback = lookback  # 用最近120个交易日的数据
    
    def calc(self, stock_df):
        vol = stock_df['volume'].tail(self.lookback)
        rng = stock_df['amplitude'].tail(self.lookback)
        return {
            # SC/BC 成交量阈值：取历史成交量的95百分位
            'climax_vol_threshold': vol.quantile(0.95),
            # SC/BC 振幅阈值：取历史振幅的95百分位
            'climax_range_threshold': rng.quantile(0.95),
            # Spring 最大穿透：取ATR(20)的1.5倍
            'spring_max_penetration': stock_df['atr_20'].iloc[-1] * 1.5,
            # ST 量能上限：SC当日量的60%（这个比例保留）
            'st_vol_ratio': 0.60,
            # 低量判定：取历史成交量的20百分位
            'low_vol_threshold': vol.quantile(0.20),
            # VDB/VSB 阈值：涨跌幅90百分位 + 量90百分位
            'vdb_price_pct': rng.quantile(0.90),
            'vdb_vol_pct': vol.quantile(0.90),
        }
```

```python
# 伪代码：似然度信号检测（替代二值判定）
class SignalLikelihood:
    """
    对每根K线计算各信号类型的似然度分数(0-1)。
    参考民生证券「概率云表达」方法论。
    """
    def calc_sc_likelihood(self, bar, context, thresholds):
        """计算当前K线是SC(抛售高潮)的似然度"""
        scores = []
        
        # 维度1: 成交量异常程度 (0-1)
        vol_ratio = bar.volume / thresholds['climax_vol_threshold']
        scores.append(min(vol_ratio, 1.0))  # 量越大分越高，封顶1.0
        
        # 维度2: 价格创新低程度 (0-1)
        if bar.low <= context.low_60d:
            scores.append(1.0)
        else:
            distance = (context.low_60d - bar.low) / context.atr_20
            scores.append(max(0, 1 - abs(distance) / 3))
        
        # 维度3: K线形态 (0-1)
        body_ratio = abs(bar.close - bar.open) / (bar.high - bar.low + 1e-9)
        lower_shadow = (min(bar.open, bar.close) - bar.low) / (bar.high - bar.low + 1e-9)
        if bar.close < bar.open:  # 阴线
            scores.append(0.5 + body_ratio * 0.3 + lower_shadow * 0.2)
        else:  # 锤子线（阳线但有长下影）
            scores.append(lower_shadow * 0.8)
        
        # 维度4: 趋势背景 (0-1) - 必须在下跌趋势中
        if context.trend == 'DOWN':
            scores.append(1.0)
        elif context.trend == 'SIDEWAYS':
            scores.append(0.3)
        else:
            scores.append(0.0)  # 上涨趋势中不可能是SC
        
        # 加权融合
        weights = [0.30, 0.25, 0.20, 0.25]
        return sum(s * w for s, w in zip(scores, weights))
    
    # 类似地实现其他12种信号的似然度计算...
    # calc_spring_likelihood(), calc_ut_likelihood(), etc.
```

#### L2: AI模糊信号判读器

当规则引擎对某根K线给出的多个信号似然度都处于中间地带（如Spring=0.45, ST=0.42）时，调用LLM进行模糊判读。

```python
# L2调用时机：当top2信号的似然度差距 < 0.15 时触发
class AISignalArbiter:
    def should_invoke(self, likelihoods: dict) -> bool:
        sorted_scores = sorted(likelihoods.values(), reverse=True)
        if len(sorted_scores) >= 2:
            return (sorted_scores[0] - sorted_scores[1]) < 0.15
        return False
    
    def arbitrate(self, bar_data, context, likelihoods, kline_image_path=None):
        prompt = f"""你是一位精通威科夫操盘法（孟洪涛版本）的A股专业交易员。
请分析以下K线数据，判断最可能的威科夫信号类型。

## 当前K线数据
- 日期: {bar_data.date}
- 开盘: {bar_data.open}, 最高: {bar_data.high}, 最低: {bar_data.low}, 收盘: {bar_data.close}
- 成交量: {bar_data.volume}（近20日均量: {context.avg_vol_20}，量比: {bar_data.volume/context.avg_vol_20:.2f}）
- 涨跌幅: {bar_data.pct_change}%
- 振幅: {bar_data.amplitude}%

## 市场背景
- 当前阶段: {context.current_phase}（置信度: {context.phase_confidence}%）
- 近期趋势: {context.trend_description}
- TR区间: {context.tr_upper} ~ {context.tr_lower}（如有）
- 近期关键事件: {context.recent_signals_summary}

## 规则引擎似然度评分
{format_likelihoods(likelihoods)}

## 要求
1. 综合以上信息，判断这根K线最可能代表的威科夫事件
2. 必须从以下选项中选择: SC, BC, AR, ST, Spring, Shakeout, JOC, SOS, SOW, UT, UTAD, SOT, DeadCorner, EvR, VDB, VSB, BreakIce, LPSY, LPS, NONE
3. 给出你的置信度(0-100)
4. 用2-3句话解释你的推理逻辑（必须引用具体的量价数据作为证据）

## 输出格式（严格JSON）
{{"signal": "XXX", "confidence": 75, "reasoning": "..."}}"""
        
        # 如果有K线截图，作为multimodal输入
        messages = [{"role": "user", "content": prompt}]
        if kline_image_path:
            # 加入图片让LLM看到图表形态
            messages = self._add_image(messages, kline_image_path)
        
        response = call_llm(messages, model="claude-sonnet-4-20250514")
        return parse_json(response)
```

#### L3: AI市场叙事引擎

这是AI创造最大价值的层——将离散的技术信号组合成连贯的「市场故事」。

```python
class MarketNarrativeEngine:
    """
    生成对当前市场状态的完整叙事理解。
    输入: 技术分析结果 + 资金流数据 + 新闻摘要
    输出: 结构化的市场叙事
    """
    def generate_narrative(self, stock_code, analysis_bundle):
        prompt = f"""你是一位资深威科夫分析师，请为{stock_code}生成当前市场状态的完整分析叙事。

## 技术面数据
- 当前威科夫阶段: {analysis_bundle.phase} (置信度: {analysis_bundle.phase_confidence}%)
- 信号链完成度: {analysis_bundle.chain_pct}%
- 已触发信号序列: {analysis_bundle.signal_chain}
- 供需评分: {analysis_bundle.sd_score}/100
- 周线阶段: {analysis_bundle.weekly_phase}
- 日线阶段: {analysis_bundle.daily_phase}

## 关键价位
- TR区间: {analysis_bundle.tr_range}
- 冰线/Creek线: {analysis_bundle.ice_creek}
- 支撑位列表: {analysis_bundle.supports}
- 阻力位列表: {analysis_bundle.resistances}
- P&F目标价: {analysis_bundle.pf_targets}

## 资金面数据
- 近5日主力资金净流入: {analysis_bundle.main_flow_5d}
- 近5日北向资金: {analysis_bundle.north_flow_5d}
- 筹码集中度: {analysis_bundle.chip_concentration}
- 获利盘比例: {analysis_bundle.profit_ratio}

## 请输出以下结构:

### 1. CM行为判读
用2-3句话描述你认为主力资金（CM）当前在做什么，基于什么证据。

### 2. 供需天平
当前供需力量对比如何？需求方和供应方各有什么表现？

### 3. 当前阶段的关键矛盾
这个阶段最需要关注的是什么？什么信号的出现会改变判断？

### 4. 情景推演
- 看多情景（概率X%）: 需要满足什么条件，目标位在哪
- 看空情景（概率Y%）: 需要满足什么条件，风险位在哪
- 中性情景（概率Z%）: 继续震荡的可能性

### 5. 行动建议
基于以上分析，给出明确的操作建议和关键观察点。"""

        response = call_llm(
            [{"role": "user", "content": prompt}],
            model="claude-sonnet-4-20250514",
            max_tokens=2000
        )
        return response
```

#### L4: AI投资建议生成器

最终输出层，融合所有层的结果生成投资建议。

```python
class AIAdvisor:
    """
    最终投资建议生成。
    将规则引擎的量化评分 + LLM的叙事分析融合为最终建议。
    """
    def generate_advice(self, stock_code, quant_scores, narrative, user_context):
        prompt = f"""基于以下量化分析和定性分析结果，为{stock_code}生成最终投资建议。

## 量化评分（规则引擎输出）
- 大盘阶段共振: {quant_scores.market_alignment}/30
- 个股阶段得分: {quant_scores.phase_score}/25
- 信号链完成度: {quant_scores.chain_score}/20
- 多时间框架共振: {quant_scores.mtf_score}/15
- 供需评分: {quant_scores.sd_score}/10
- 量化总分: {quant_scores.total}/100

## 九大买入检验结果（威科夫）
{format_nine_tests(quant_scores.nine_tests)}
通过项数: {quant_scores.nine_tests_passed}/9

## 定性分析（L3叙事引擎输出）
{narrative}

## 用户持仓上下文
- 当前是否持有该股: {user_context.holding}
- 持仓成本: {user_context.cost_price}
- 持仓天数: {user_context.holding_days}
- 账户总风险敞口: {user_context.total_risk_pct}%

## 请生成以下结构化建议（严格JSON）:
{{
  "advice_type": "STRONG_BUY|BUY|WATCH|HOLD|REDUCE|SELL|STRONG_SELL|WAIT",
  "confidence": 0-100,
  "summary": "一句话核心建议",
  "reasoning": "3-5句话的推理逻辑，引用具体数据和信号",
  "trade_plan": {{
    "entry_price": null或具体价格,
    "stop_loss": null或具体价格,
    "target_1": null或具体价格（保守目标）,
    "target_2": null或具体价格（进取目标）,
    "position_pct": 建议仓位比例(0-100),
    "rr_ratio": 风险回报比
  }},
  "key_watch_points": ["需要观察的关键事项1", "关键事项2"],
  "invalidation": "什么情况下这个建议失效",
  "valid_until": "建议有效期（交易日数）"
}}"""

        response = call_llm(
            [{"role": "user", "content": prompt}],
            model="claude-sonnet-4-20250514",
            max_tokens=1500
        )
        return parse_json(response)
```

### 2.4 LLM调用策略与成本控制

| 层级 | 调用频率 | 模型选择 | 单次Token | 日均调用次数（20只自选股） |
|------|---------|---------|-----------|------------------------|
| L1 | 每根K线 | 无LLM | 0 | 0 |
| L2 | 仅模糊信号时触发（约5%的K线） | claude-sonnet-4-20250514 | ~800 | ~20次 |
| L3 | 每日收盘后批量执行 | claude-sonnet-4-20250514 | ~1500 | 20次 |
| L4 | L3完成后 + 手动触发 | claude-sonnet-4-20250514 | ~1000 | ~20次 |
| **日均总计** | | | | **~60次，约10万token/天** |

---

## 第三部分：补全遗漏的策略组件

### 3.1 威科夫九大买入检验（Nine Buying Tests）

这是原书中明确要求的系统化检验工具，V1.0和V2.0均遗漏。

```python
class NineBuyingTests:
    """
    威科夫九大买入检验。
    所有检验通过=理想买点。实战中通常6-7项通过即可考虑入场。
    """
    def evaluate(self, stock, context, thresholds):
        results = {}
        
        # 1. 下跌目标是否已达到（P&F计数法目标位）
        results['T1_target_reached'] = {
            'name': '下跌目标价已达到',
            'passed': stock.low <= context.pf_downside_target * 1.02,
            'detail': f'P&F目标: {context.pf_downside_target}, 实际最低: {stock.low}'
        }
        
        # 2. 是否出现PS, SC, AR, ST序列
        results['T2_stopping_action'] = {
            'name': '出现停止行为序列(PS→SC→AR→ST)',
            'passed': context.has_stopping_sequence,
            'detail': f'已出现: {context.stopping_events}'
        }
        
        # 3. 看涨交易活动（上涨放量、回调缩量）
        results['T3_bullish_activity'] = {
            'name': '看涨量价关系（反弹放量、回调缩量）',
            'passed': context.up_vol_trend > context.down_vol_trend,
            'detail': f'上涨波段均量: {context.up_vol_trend}, 下跌波段均量: {context.down_vol_trend}'
        }
        
        # 4. 初次支撑形成（底部支撑稳固，SOT出现）
        results['T4_support_formed'] = {
            'name': '支撑位确立（多次测试不破）',
            'passed': context.support_test_count >= 2 and not context.support_broken,
            'detail': f'支撑测试次数: {context.support_test_count}'
        }
        
        # 5. 供应枯竭（低量测试支撑，缩量回调）
        results['T5_supply_dried'] = {
            'name': '供应枯竭（低量回调、缩量测试）',
            'passed': context.last_test_vol < thresholds['low_vol_threshold'],
            'detail': f'最近测试量: {context.last_test_vol}, 低量阈值: {thresholds["low_vol_threshold"]}'
        }
        
        # 6. 相对强度（强于大盘）
        results['T6_relative_strength'] = {
            'name': '个股强于大盘',
            'passed': context.relative_strength > 1.0,
            'detail': f'相对强度: {context.relative_strength:.2f}'
        }
        
        # 7. 底部形态形成（Spring或震仓已确认）
        results['T7_spring_or_shakeout'] = {
            'name': 'Spring或震仓已确认',
            'passed': context.spring_confirmed or context.shakeout_confirmed,
            'detail': f'Spring: {context.spring_confirmed}, 震仓: {context.shakeout_confirmed}'
        }
        
        # 8. 趋势线突破或SOS出现
        results['T8_trend_change'] = {
            'name': '下降趋势线突破或SOS出现',
            'passed': context.downtrend_broken or context.sos_detected,
            'detail': f'趋势线突破: {context.downtrend_broken}, SOS: {context.sos_detected}'
        }
        
        # 9. 因果关系充分（TR横盘时间足够）
        results['T9_cause_sufficient'] = {
            'name': '因果关系充分（TR时间≥30日）',
            'passed': context.tr_duration >= 30,
            'detail': f'TR持续天数: {context.tr_duration}'
        }
        
        passed_count = sum(1 for r in results.values() if r['passed'])
        return {
            'tests': results,
            'passed_count': passed_count,
            'total': 9,
            'recommendation': 'BUY' if passed_count >= 7 else 'WATCH' if passed_count >= 5 else 'WAIT'
        }
```

### 3.2 供需评分公式（明确化）

```python
class SupplyDemandScore:
    """
    供需力量评分: -100(极端供应主导) 到 +100(极端需求主导)
    六个维度加权计算。
    """
    def calculate(self, stock, context):
        scores = {}
        
        # 1. 量价关系 (权重30%) —— 上涨波段vs下跌波段的量价对比
        up_power = context.avg_up_vol * context.avg_up_range
        down_power = context.avg_down_vol * context.avg_down_range
        vp_ratio = (up_power - down_power) / (up_power + down_power + 1e-9)
        scores['volume_price'] = vp_ratio * 100  # -100 to +100
        
        # 2. K线形态 (权重20%) —— 近10日阳线占比和实体强度
        bull_bars = sum(1 for b in context.last_10_bars if b.close > b.open)
        bar_score = (bull_bars / 10 - 0.5) * 200
        scores['bar_pattern'] = max(-100, min(100, bar_score))
        
        # 3. 趋势位置 (权重15%) —— 价格在趋势通道中的位置
        if context.channel_exists:
            channel_pos = (stock.close - context.channel_lower) / (context.channel_upper - context.channel_lower + 1e-9)
            scores['trend_position'] = (channel_pos - 0.5) * 200
        else:
            scores['trend_position'] = 0
        
        # 4. 北向资金/主力资金 (权重15%)
        flow_score = context.north_flow_5d_normalized  # 已标准化到-100~+100
        scores['smart_money'] = flow_score
        
        # 5. 维斯波力量对比 (权重10%)
        weis_score = context.weis_wave_balance  # 上涨波量vs下跌波量
        scores['weis_wave'] = weis_score
        
        # 6. 停止行为检测 (权重10%) —— 是否出现EvR/SOT等停止信号
        if context.recent_evr_bullish:  # 放量滞跌（看涨停止行为）
            scores['stopping'] = 80
        elif context.recent_evr_bearish:  # 放量滞涨（看跌停止行为）
            scores['stopping'] = -80
        else:
            scores['stopping'] = 0
        
        weights = {
            'volume_price': 0.30,
            'bar_pattern': 0.20,
            'trend_position': 0.15,
            'smart_money': 0.15,
            'weis_wave': 0.10,
            'stopping': 0.10,
        }
        
        final = sum(scores[k] * weights[k] for k in weights)
        return round(final, 1), scores
```

### 3.3 维斯波（Weis Wave）实现

```python
class WeisWave:
    """
    David Weis发展的波量分析工具。
    将连续同向K线聚合为一个"波"，累计该波的总成交量。
    用于直观对比上涨波和下跌波的量能强弱。
    """
    def calculate(self, bars, min_reversal_pct=0.02):
        waves = []
        current_direction = None  # 'UP' or 'DOWN'
        wave_start_price = bars[0].close
        wave_volume = 0
        wave_bars = 0
        
        for bar in bars:
            if current_direction is None:
                current_direction = 'UP' if bar.close >= bar.open else 'DOWN'
                wave_volume = bar.volume
                wave_bars = 1
                wave_start_price = bar.open
                continue
            
            # 判断方向变化
            price_change = (bar.close - wave_start_price) / wave_start_price
            
            if current_direction == 'UP' and bar.close < bar.open:
                reversal_pct = abs(bar.close - bars[bars.index(bar)-1].high) / bars[bars.index(bar)-1].high
                if reversal_pct >= min_reversal_pct:
                    waves.append({
                        'direction': current_direction,
                        'volume': wave_volume,
                        'bars': wave_bars,
                        'price_change': price_change,
                    })
                    current_direction = 'DOWN'
                    wave_volume = bar.volume
                    wave_bars = 1
                    wave_start_price = bar.open
                    continue
            
            elif current_direction == 'DOWN' and bar.close > bar.open:
                reversal_pct = abs(bar.close - bars[bars.index(bar)-1].low) / bars[bars.index(bar)-1].low
                if reversal_pct >= min_reversal_pct:
                    waves.append({
                        'direction': current_direction,
                        'volume': wave_volume,
                        'bars': wave_bars,
                        'price_change': price_change,
                    })
                    current_direction = 'UP'
                    wave_volume = bar.volume
                    wave_bars = 1
                    wave_start_price = bar.open
                    continue
            
            wave_volume += bar.volume
            wave_bars += 1
        
        return waves
    
    def analyze_balance(self, waves, recent_n=6):
        """分析最近N个波的多空力量对比"""
        recent = waves[-recent_n:] if len(waves) >= recent_n else waves
        up_waves = [w for w in recent if w['direction'] == 'UP']
        down_waves = [w for w in recent if w['direction'] == 'DOWN']
        
        avg_up_vol = sum(w['volume'] for w in up_waves) / max(len(up_waves), 1)
        avg_down_vol = sum(w['volume'] for w in down_waves) / max(len(down_waves), 1)
        
        # 返回-100到+100的平衡值
        balance = (avg_up_vol - avg_down_vol) / (avg_up_vol + avg_down_vol + 1e-9) * 100
        return round(balance, 1)
```

---

## 第四部分：完整系统架构与开发规范

### 4.1 项目结构

```
wyckoffpro/
├── main.py                     # 入口文件，启动Streamlit/Web UI
├── config/
│   ├── default.yaml            # 默认配置（所有可配置阈值）
│   ├── presets/                 # 参数预设（主板/创业板/科创板）
│   └── watchlist.json          # 自选股列表
├── data/
│   ├── collector.py            # M1: 数据采集（Tushare/AKShare适配器）
│   ├── storage.py              # SQLite存储层
│   ├── cleaner.py              # 数据清洗（复权、停牌处理）
│   └── schema.sql              # 数据库Schema
├── engine/
│   ├── thresholds.py           # 自适应阈值计算器
│   ├── phase_fsm.py            # M2: 阶段识别有限状态机
│   ├── signal_detector.py      # M3: 13种信号的似然度计算
│   ├── signal_chain.py         # M3: 复合信号链追踪器
│   ├── nine_tests.py           # 九大买入/卖出检验
│   ├── supply_demand.py        # 供需评分计算器
│   ├── weis_wave.py            # 维斯波计算
│   ├── pnf_chart.py            # M10: 点数图 + 计数法目标价
│   ├── channel.py              # 趋势通道 + 超买超卖线 + 50%原则
│   └── mtf_analyzer.py         # 多时间框架分析器
├── ai/
│   ├── llm_client.py           # LLM调用封装（支持Anthropic API）
│   ├── signal_arbiter.py       # L2: AI模糊信号判读器
│   ├── narrative_engine.py     # L3: AI市场叙事引擎
│   ├── advisor.py              # L4: AI投资建议生成器
│   └── prompts/                # Prompt模板文件
│       ├── signal_arbitrate.md
│       ├── narrative.md
│       └── advice.md
├── trade/
│   ├── plan_generator.py       # M5: 交易计划生成（6种进场模式）
│   ├── risk_manager.py         # M6: 风险管理（仓位/止损/移动止损）
│   └── position_tracker.py     # 持仓跟踪
├── backtest/
│   ├── engine.py               # M7: 回测引擎
│   ├── metrics.py              # 绩效指标计算
│   └── optimizer.py            # 参数优化
├── ui/
│   ├── app.py                  # Streamlit主应用
│   ├── pages/
│   │   ├── dashboard.py        # 主看盘页
│   │   ├── scanner.py          # 全市场扫描
│   │   ├── analysis.py         # 个股深度分析
│   │   ├── plans.py            # 交易计划管理
│   │   ├── backtest.py         # 回测页面
│   │   └── settings.py         # 配置页面
│   ├── components/
│   │   ├── kline_chart.py      # K线图组件（TradingView封装）
│   │   ├── pnf_chart.py        # 点数图组件
│   │   ├── signal_panel.py     # 信号面板
│   │   ├── advice_card.py      # 投资建议卡片
│   │   └── phase_bar.py        # 阶段色带组件
│   └── static/                 # 静态资源
├── tests/                      # 测试
│   ├── test_signals.py
│   ├── test_phase_fsm.py
│   ├── test_nine_tests.py
│   └── fixtures/               # 测试数据（历史K线样本）
├── requirements.txt
└── README.md
```

### 4.2 SQLite Schema

```sql
-- 日K线数据
CREATE TABLE kline_daily (
    stock_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,    -- YYYY-MM-DD
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER,             -- 手
    amount REAL,                -- 元
    turnover_rate REAL,         -- %
    pct_change REAL,            -- %
    amplitude REAL,             -- %
    PRIMARY KEY (stock_code, trade_date)
);
CREATE INDEX idx_kline_code ON kline_daily(stock_code);
CREATE INDEX idx_kline_date ON kline_daily(trade_date);

-- 威科夫阶段
CREATE TABLE wyckoff_phase (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    phase_code TEXT NOT NULL,    -- ACC-A, ACC-B, ..., MKU, DIS-A, ..., MKD
    start_date TEXT NOT NULL,
    end_date TEXT,               -- NULL = 进行中
    confidence REAL,             -- 0-100
    tr_upper REAL, tr_lower REAL,
    ice_line REAL, creek_line REAL,
    timeframe TEXT DEFAULT 'daily',  -- daily/weekly/60min
    UNIQUE(stock_code, start_date, timeframe)
);

-- 威科夫信号
CREATE TABLE wyckoff_signal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    signal_date TEXT NOT NULL,
    signal_type TEXT NOT NULL,   -- SC, Spring, JOC, UT, ...
    likelihood REAL NOT NULL,    -- 0.0 - 1.0 似然度
    strength INTEGER,            -- 1-5
    phase_code TEXT,
    trigger_price REAL,
    trigger_volume INTEGER,
    is_confirmed INTEGER DEFAULT 0,
    confirm_date TEXT,
    ai_reasoning TEXT,           -- L2 AI判读的推理（如有）
    rule_detail TEXT,            -- JSON: 各维度得分明细
    timeframe TEXT DEFAULT 'daily'
);
CREATE INDEX idx_signal_code_date ON wyckoff_signal(stock_code, signal_date);

-- 信号链追踪
CREATE TABLE signal_chain (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    chain_type TEXT NOT NULL,    -- ACCUMULATION / DISTRIBUTION
    start_date TEXT NOT NULL,
    events TEXT NOT NULL,        -- JSON: 已触发事件列表
    completion_pct INTEGER,      -- 0-100
    status TEXT DEFAULT 'ACTIVE', -- ACTIVE / COMPLETED / FAILED
    timeframe TEXT DEFAULT 'daily'
);

-- 投资建议
CREATE TABLE advice (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    created_at TEXT NOT NULL,
    advice_type TEXT NOT NULL,   -- STRONG_BUY, BUY, WATCH, HOLD, REDUCE, SELL, STRONG_SELL, WAIT
    confidence REAL,
    summary TEXT,
    reasoning TEXT,
    trade_plan TEXT,             -- JSON
    key_watch_points TEXT,       -- JSON
    invalidation TEXT,
    valid_until TEXT,
    quant_score REAL,
    nine_tests_passed INTEGER,
    narrative TEXT,              -- L3叙事引擎输出
    is_expired INTEGER DEFAULT 0
);

-- 交易计划
CREATE TABLE trade_plan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    direction TEXT NOT NULL,     -- LONG / SHORT
    entry_mode TEXT,             -- EP-01 to EP-06
    entry_price REAL,
    stop_loss REAL,
    target_1 REAL,
    target_2 REAL,
    rr_ratio REAL,
    position_pct REAL,
    status TEXT DEFAULT 'DRAFT', -- DRAFT/ACTIVE/TRIGGERED/CLOSED
    linked_advice_id INTEGER,
    created_at TEXT,
    notes TEXT,
    FOREIGN KEY(linked_advice_id) REFERENCES advice(id)
);

-- 自选股
CREATE TABLE watchlist (
    stock_code TEXT NOT NULL,
    group_name TEXT DEFAULT 'default',
    added_at TEXT,
    notes TEXT,
    PRIMARY KEY(stock_code, group_name)
);
```

### 4.3 关键配置文件 default.yaml

```yaml
# WyckoffPro 默认配置

data:
  source: tushare          # tushare / akshare
  tushare_token: ""        # 需要用户填入自己的token
  history_years: 5         # 历史数据保留年数
  update_schedule: "15:30" # 每日自动更新时间

thresholds:
  # 以下为默认值，系统会用自适应阈值覆盖
  # 仅在自适应阈值计算失败时作为fallback
  climax_vol_percentile: 95     # 高潮量能百分位
  climax_range_percentile: 95   # 高潮振幅百分位
  spring_max_penetration_atr: 1.5  # Spring最大穿透（ATR倍数）
  st_vol_ratio: 0.60            # ST量 ≤ SC/BC量的比例
  tr_min_duration: 20           # TR最短持续天数
  tr_max_amplitude: 0.25        # TR最大振幅（相对下沿）
  joc_vol_percentile: 85        # JOC突破量能百分位
  sot_shrink_ratio: 0.50        # SOT突破缩小判定比例
  evr_vol_multiplier: 1.5       # EvR量能放大倍数
  dead_corner_min_bars: 8       # 死角最少K线数
  dead_corner_range_ratio: 0.40 # 死角振幅缩小比例
  
  # 自适应阈值参数
  adaptive_lookback: 120        # 自适应回看天数
  adaptive_enabled: true        # 是否启用自适应

phase_fsm:
  # 阶段转移需要的最小证据数量
  min_evidence_for_transition: 2
  # 异常转移触发告警的阈值
  anomaly_transition_alert: true

signals:
  # 似然度阈值
  min_likelihood_to_record: 0.30  # 低于此值不记录
  min_likelihood_for_alert: 0.60  # 高于此值触发提醒
  ambiguity_threshold: 0.15       # top2差距小于此值触发L2 AI判读
  
  # 信号链
  chain_watch_threshold: 60       # 完成度≥此值开始重点关注
  chain_advice_threshold: 85      # 完成度≥此值触发建议生成

nine_tests:
  min_pass_for_buy: 7            # 买入检验最少通过数
  min_pass_for_watch: 5          # 关注检验最少通过数

risk:
  max_single_risk_pct: 2.0       # 单笔最大风险比例(%)
  max_total_risk_pct: 10.0       # 总仓位最大风险(%)
  min_rr_ratio: 3.0              # 最小风险回报比（威科夫要求≥3）
  t1_overnight_premium: 0.005    # T+1隔夜风险溢价(0.5%)

ai:
  enabled: true
  api_provider: anthropic        # anthropic
  model: claude-sonnet-4-20250514
  max_tokens: 2000
  l2_enabled: true               # 模糊信号AI判读
  l3_enabled: true               # 市场叙事AI分析
  l4_enabled: true               # AI投资建议生成
  daily_token_budget: 200000     # 日Token预算

ui:
  theme: dark                    # dark / light
  default_period: daily          # 默认K线周期
  chart_style: candle            # candle / bar
  alert_sound: true
  
a_share_adapt:
  enabled: true
  limit_up_as_bc: true           # 涨停视为BC变体
  limit_down_as_sc: true         # 跌停视为SC变体
  north_flow_weight: 0.15        # 北向资金在供需评分中的权重
  chip_data_enabled: false       # 筹码数据（需额外数据源）
  t1_entry_delay: true           # T+1入场延迟（信号日次日开盘入场）
```

### 4.4 开发优先级与里程碑

```
Phase 1 (W1-W6): 核心引擎 + AI基础
  W1: M1数据采集 + SQLite + 数据清洗
  W2: engine/thresholds.py + engine/weis_wave.py + engine/supply_demand.py
  W3: engine/signal_detector.py (13种信号似然度) + engine/phase_fsm.py
  W4: engine/signal_chain.py + engine/nine_tests.py + engine/channel.py
  W5: ai/llm_client.py + ai/signal_arbiter.py + ai/narrative_engine.py + ai/advisor.py
  W6: ui/dashboard.py (K线图+阶段色带+信号标记+建议卡片) 联调

Phase 2 (W7-W10): 交易计划 + 点数图 + 多时间框架
  W7: engine/pnf_chart.py + engine/mtf_analyzer.py
  W8: trade/plan_generator.py + trade/risk_manager.py
  W9: ui/scanner.py + ui/analysis.py + ui/plans.py
  W10: A股适配层完善 + 全系统联调

Phase 3 (W11-W14): 回测 + 优化
  W11-W12: backtest/engine.py + backtest/metrics.py
  W13: backtest/optimizer.py + 参数调优
  W14: 全面测试 + 文档 + 性能优化
```

### 4.5 技术栈确认

```
requirements.txt:
  # 核心
  python>=3.11
  pandas>=2.0
  numpy>=1.24
  ta-lib                  # 技术指标库（需先安装C库）
  
  # 数据源
  tushare>=1.2.89
  akshare>=1.10           # 备用数据源
  
  # 数据库
  # SQLite内置，无需安装
  
  # AI
  anthropic>=0.25         # Anthropic Python SDK
  
  # UI
  streamlit>=1.30
  streamlit-lightweight-charts>=0.8  # TradingView K线图
  plotly>=5.18            # P&F图表/回测图表
  
  # ML（Phase 2）
  lightgbm>=4.0
  scikit-learn>=1.3
  
  # 工具
  pyyaml>=6.0
  schedule>=1.2           # 定时任务
  loguru>=0.7             # 日志
```

---

## 第五部分：AI开发专用指令

以下内容供直接粘贴给AI编码助手使用：

### 5.1 项目初始化指令

```
请创建一个Python项目 wyckoffpro，基于以下技术栈：
- Python 3.11+, Streamlit, Pandas, NumPy, SQLite
- Anthropic API (claude-sonnet-4-20250514)

项目是一个个人自用的A股量价分析工具，核心理论是孟洪涛版威科夫操盘法。
系统通过量价数据自动识别威科夫四阶段（吸筹/拉升/派发/下跌），
检测13种关键信号，融合AI大模型生成投资建议。

请按照上述项目结构创建目录和空文件，并实现 config/default.yaml 的配置加载。
```

### 5.2 各模块开发指令模板

开发每个模块时，向AI提供：

1. 本文档对应章节的完整内容
2. 该模块的输入/输出数据结构
3. 伪代码（如有）
4. 需要调用的其他模块接口

示例（开发信号检测模块时）：

```
请实现 engine/signal_detector.py，要求：

1. 实现 SignalLikelihood 类，对每根K线计算13种威科夫信号的似然度分数(0.0-1.0)
2. 13种信号: SC, BC, AR, ST, Spring, Shakeout, JOC, SOS, SOW, UT, UTAD, SOT, DeadCorner
3. 每种信号的似然度由多个维度加权计算（参考本文档第三部分的伪代码）
4. 使用自适应阈值（从 engine/thresholds.py 获取）而非固定倍数
5. 输出格式: dict[str, float]，key为信号类型，value为似然度
6. 当top2信号似然度差距 < config.signals.ambiguity_threshold 时，
   标记 needs_ai_arbitration=True

关键约束:
- SC只能在下跌趋势中触发
- Spring只能在已识别的TR区间下方触发
- JOC只能在Phase ACC-D触发
- UT只能在Phase DIS-B/C触发
- 这些约束由 engine/phase_fsm.py 的当前状态提供
```

---

*本文档为WyckoffPro系统的终版开发指导，涵盖策略审查修正、AI融合架构、补全的策略组件、完整项目结构和开发规范。可直接用于指导AI进行模块化开发。*
