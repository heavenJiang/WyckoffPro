# WyckoffPro 开发指导文档（V3.1 合并终稿）

> **文档性质**：可直接交给AI（Claude/Cursor/Copilot）进行代码生成的开发指导书  
> **理论基础**：孟洪涛《威科夫操盘法》+《新威科夫操盘法》完整体系  
> **系统定位**：个人自用本地交易分析工具，生成投资建议，不自动下单  
> **版本**：V3.1（合并FSM紧急反转补丁 + 证伪式Prompt架构补丁）  
> **日期**：2026-04-04

---

## 版本沿革

| 版本 | 变更 |
|------|------|
| V1.0 | 初版PRD，商用SaaS架构 |
| V2.0 | 修正为自用定位，新增点数图/死角/多时间框架/投资建议引擎 |
| V3.0 | 策略有效性审查，引入自适应阈值/似然度模型/九大检验/维斯波/AI四层架构 |
| **V3.1** | **合并两大补丁：①FSM紧急反转路径（反面证据积分+假设推翻机制）②证伪式Prompt架构（LLM从「给结论」转为「尝试推翻结论」）** |

---

## 第一部分：策略有效性审查与修正

### 1.1 历次审查发现的核心问题

| 编号 | 问题描述 | 严重程度 | 修正版本 |
|------|---------|---------|---------|
| S01 | 固定阈值不适应不同股票特性 | 高 | V3.0：自适应百分位数阈值 |
| S02 | 信号判定是二值的而非概率性的 | 高 | V3.0：似然度/概率云模型 |
| S03 | 缺少威科夫九大买入/卖出检验 | 高 | V3.0：完整实现 |
| S04 | 未引入维斯波（Weis Wave） | 中 | V3.0：波量聚合分析 |
| S05 | 目标价只有P&F一种方法 | 中 | V3.0：多目标位融合 |
| S06 | 供需评分缺少具体公式 | 中 | V3.0：六维度加权公式 |
| S07 | AI能力完全缺失 | 高 | V3.0：四层AI架构 |
| **S08** | **FSM缺少紧急反转路径：一旦进入吸筹假设就无法自我推翻，即使累积大量反面证据** | **致命** | **V3.1：反面证据积分+紧急反转机制** |
| **S09** | **AI采用归纳式（给结论），导致确认偏误——LLM顺着FSM假设走而非检验假设** | **高** | **V3.1：证伪式Prompt架构** |

### 1.2 V3.1新增修正方案

| 修正 | 方案 |
|------|------|
| S08 → **FSM紧急反转** | 反面证据积分机制（0-100），黄→橙→红三级预警，积分≥71触发阶段假设推翻；新增TR_UNDETERMINED中性待判定状态 |
| S09 → **证伪式Prompt** | LLM角色从「给出结论」变为「尝试推翻FSM结论」；三层证伪（阶段证伪/信号证伪/叙事一致性检验）；证伪结果直接驱动反面证据积分和建议门控 |

---

## 第二部分：AI/大模型融合架构（证伪式，V3.1重构）

### 2.1 核心理念转变

| 维度 | V3.0（归纳式） | V3.1（证伪式） |
|------|--------------|--------------|
| LLM的角色 | 给出结论 | 尝试推翻结论 |
| 认识论 | 归纳法（正面确认） | 证伪法（反面检验） |
| 确认偏误风险 | 高（LLM顺着FSM假设走） | 低（LLM被要求反着走） |
| 输出类型 | 信号类型+置信度 | 矛盾列表+替代假设+严重程度 |
| 与FSM的关系 | 并行（两套结论可能冲突） | 串行（FSM先判，LLM后验） |
| 与反面证据积分 | 无连接 | 深度集成（证伪结果直接驱动积分） |
| 对建议的影响 | 间接 | 直接（门控可BLOCK建议） |

**为什么证伪式更适合威科夫分析？**

孟洪涛书中的方法论本身就是证伪优先的：

| 书中原则 | 证伪本质 |
|---------|---------|
| "市场应该做什么但没有做，这是个警告" | 预期与现实不一致 → 假设可能有误 |
| "努力没有结果是一种停止行为" | 量（努力）与价（结果）的不一致 → 趋势假设可能有误 |
| "如果你在震荡区内做多了，看到这些情况，必须离场" | 持续寻找与持仓假设矛盾的证据 |
| "不能盲目抄底"——即使出现了类似SC的行为 | 单一正面信号不足以确认假设，必须排除反面可能 |

### 2.2 V3.1四层架构

```
┌─────────────────────────────────────────────────────────────┐
│  L4: AI投资建议生成器（最终输出层）                            │
│  输入: L1量化评分 + L2-F证伪结果 + 用户持仓上下文              │
│  门控: 证伪引擎可BLOCK/DOWNGRADE建议                          │
├─────────────────────────────────────────────────────────────┤
│  L2-F: 证伪引擎（Falsification Engine）—— V3.1核心新增        │
│  ┌────────────┐ ┌────────────┐ ┌─────────────────┐         │
│  │ Prompt A:  │ │ Prompt B:  │ │ Prompt C:       │         │
│  │ 阶段证伪   │ │ 信号证伪   │ │ 叙事一致性检验   │         │
│  │ "推翻阶段  │ │ "推翻这个  │ │ "整体故事       │         │
│  │  假设"     │ │  Spring"   │ │  是否自洽？"     │         │
│  └─────┬──────┘ └─────┬──────┘ └────────┬────────┘         │
│        └──────────────┼─────────────────┘                   │
│                       ▼                                     │
│        ┌─────────────────────────────┐                      │
│        │ 证伪结果聚合器               │                      │
│        │ → 反面证据积分调整           │                      │
│        │ → 信号似然度修正             │                      │
│        │ → 建议门控（PASS/BLOCK）     │                      │
│        └─────────────────────────────┘                      │
├─────────────────────────────────────────────────────────────┤
│  L1: 规则引擎 + FSM + 反面证据追踪器（基础计算层）            │
│  纯Python/NumPy，不依赖LLM                                   │
│  输出: 阶段判定 + 信号似然度 + 反面证据积分 + 供需评分        │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 L1: 规则引擎 + FSM（基础层，无LLM依赖）

这一层是系统的骨架，即使LLM不可用也能独立运行。

#### 2.3.1 自适应阈值

```python
class AdaptiveThresholds:
    """每只股票基于自身历史数据动态计算阈值，替代固定倍数。"""
    def __init__(self, lookback=120):
        self.lookback = lookback
    
    def calc(self, stock_df):
        vol = stock_df['volume'].tail(self.lookback)
        rng = stock_df['amplitude'].tail(self.lookback)
        return {
            'climax_vol_threshold': vol.quantile(0.95),
            'climax_range_threshold': rng.quantile(0.95),
            'spring_max_penetration': stock_df['atr_20'].iloc[-1] * 1.5,
            'st_vol_ratio': 0.60,
            'low_vol_threshold': vol.quantile(0.20),
            'vdb_price_pct': rng.quantile(0.90),
            'vdb_vol_pct': vol.quantile(0.90),
        }
```

#### 2.3.2 似然度信号检测

```python
class SignalLikelihood:
    """对每根K线计算各信号的似然度分数(0-1)。参考民生证券「概率云表达」。"""
    
    def calc_sc_likelihood(self, bar, context, thresholds):
        scores = []
        # 维度1: 成交量异常程度 (权重0.30)
        vol_ratio = bar.volume / thresholds['climax_vol_threshold']
        scores.append(min(vol_ratio, 1.0))
        # 维度2: 价格创新低程度 (权重0.25)
        scores.append(1.0 if bar.low <= context.low_60d else max(0, 1 - abs(context.low_60d - bar.low) / context.atr_20 / 3))
        # 维度3: K线形态 (权重0.20)
        body = abs(bar.close - bar.open) / (bar.high - bar.low + 1e-9)
        shadow = (min(bar.open, bar.close) - bar.low) / (bar.high - bar.low + 1e-9)
        scores.append(0.5 + body*0.3 + shadow*0.2 if bar.close < bar.open else shadow*0.8)
        # 维度4: 趋势背景 (权重0.25)
        scores.append({'DOWN':1.0, 'SIDEWAYS':0.3}.get(context.trend, 0.0))
        
        weights = [0.30, 0.25, 0.20, 0.25]
        return sum(s*w for s,w in zip(scores, weights))
    
    # 类似实现其他12种信号: calc_spring_likelihood(), calc_ut_likelihood(), ...
```

### 2.4 L2-F: 证伪引擎（V3.1核心新增）

#### 2.4.1 Prompt A — 阶段证伪

```markdown
# 角色
你是一位被雇来专门"唱反调"的威科夫高级分析师。你的任务不是确认当前判断，
而是竭尽全力寻找证据来推翻它。你因为成功发现错误判断而获得奖励，
因为遗漏反面证据而受到惩罚。

# 当前假设（你需要尝试推翻的）
系统FSM判定 {stock_code} 当前处于 **{phase_code}**（{phase_name}）阶段。
阶段起始日期: {phase_start_date}
FSM置信度: {phase_confidence}%

# 原始数据（最近{N}根K线）
{kline_table}

# FSM判定依据
{fsm_evidence_chain}

# 你的任务
## Step 1: 列出该阶段假设的必要条件
根据孟洪涛版威科夫理论，{phase_code}阶段**必须满足**哪些条件？逐条列出（至少5条）。

## Step 2: 逐条检验
对每个必要条件，检查原始数据是否真的满足。特别关注：
- 量价关系是否真的支持这个阶段？
- 有没有"应该出现但没出现"的行为？
- 有没有"不应该出现却出现了"的行为？
- 时间维度：这个阶段持续的时间是否合理？

## Step 3: 提出替代假设
如果当前判定是错的，最可能的真实阶段是什么？

## Step 4: 输出严格JSON
{
  "falsification_result": "FAILED" 或 "SUCCEEDED" 或 "PARTIAL",
  "confidence_in_falsification": 0-100,
  "violated_conditions": [
    {"condition": "...", "expected": "...", "actual": "...", "severity": "CRITICAL/MAJOR/MINOR"}
  ],
  "alternative_hypothesis": {"phase": "...", "reasoning": "...", "confidence": 0-100},
  "overall_assessment": "一段话总结"
}

# 关键规则
- 必须认真尝试推翻，不要轻易说"无法推翻"
- 引用具体日期和数值，不泛泛而谈
- "没有异常"不等于"假设正确"——主动寻找缺失的确认信号
- 如果确实找不到反面证据，诚实报告FAILED
```

**调用时机**：阶段首次判定时、阶段持续超30日、反面积分达黄色(31)/橙色(51)阈值、用户手动触发。

#### 2.4.2 Prompt B — 信号证伪

```markdown
# 角色
你是威科夫信号质量审计员。规则引擎检测到了一个信号，
你的工作是检查这个信号是否是"假信号"。

# 待检验信号
类型: {signal_type}, 日期: {signal_date}, 似然度: {likelihood}
触发价格: {trigger_price}, 触发成交量: {trigger_volume}（{vol_ratio:.1f}倍均量）

# 市场背景
当前阶段: {current_phase}, TR区间: {tr_upper}~{tr_lower}
近期信号序列: {recent_signals}, 供需评分: {sd_score}

# 前后K线数据（信号日前10根 + 信号日 + 信号日后3根）
{kline_context_table}

# 证伪检查清单
{signal_specific_checklist}

# 输出严格JSON
{
  "signal_type": "{signal_type}",
  "falsification_result": "GENUINE" 或 "SUSPECT" 或 "FALSE",
  "confidence": 0-100,
  "checks": [{"check_item": "...", "passed": true/false, "evidence": "..."}],
  "if_false_then": "如果是假信号，真正含义是什么",
  "recommendation": "后续操作建议"
}
```

**各信号类型的专用证伪检查清单**：

**Spring检查清单**：①穿透深度是否超过ATR 2倍（超过=有效突破非Spring）②3根K线内是否收回支撑上方 ③低量是否真实供应枯竭而非节假日效应 ④Spring后是否有缩量ST确认 ⑤吸筹Phase B是否持续≥20日（因充分否）⑥大盘是否暴跌中（Spring更易被击穿）⑦Spring前是否有EvR停止行为铺垫

**SC检查清单**：①是否只是正常熊市中的一次放量（非高潮级别）②下跌是否足够"恐慌"（连续阴线+加速）③SC后AR是否真的出现 ④从高点下跌幅度是否≥30% ⑤同板块是否也出现底部行为

**JOC检查清单**：①突破日量是否近期最大之一 ②突破后1-3日是否立刻回落（假突破=UT）③回测是否真的缩量 ④九大检验通过几项 ⑤TR持续时间/宽度是否足够支撑后续行情

**SOW检查清单**：①是否是吸筹区的正常震仓（跌后快速反弹=震仓非SOW）②SOW后是否继续走弱 ③冰线是否真的被有效跌破（收盘价确认）④SOW后反弹是否确实无量

**调用时机**：似然度0.50-0.75的所有信号、用于生成交易计划的关键入场信号（Spring/JOC/破冰/LPSY）、与阶段存在逻辑张力的信号（如ACC中出现SOW）、用户手动触发。

#### 2.4.3 Prompt C — 叙事一致性检验

```markdown
# 角色
你是审阅威科夫分析报告的高级编辑。
检查这份报告在逻辑上是否自洽、是否存在自相矛盾。

# 完整分析判定
- 周线阶段: {weekly_phase}（{weekly_conf}%）
- 日线阶段: {daily_phase}（{daily_conf}%）
- 60分钟线阶段: {intra_phase}（{intra_conf}%）
- 信号链: {chain_type}，完成度{chain_pct}%，事件: {signal_chain_timeline}
- 关键价位: 支撑{supports}, 阻力{resistances}, 冰线{ice_line}, Creek{creek_line}
- 供需评分: {sd_score}，维度: {sd_breakdown}
- 当前建议: {current_advice}
- 反面证据: 积分{counter_score}/100，级别{alert_level}

# 一致性检查
1. 多时间框架是否一致（周线下跌+日线吸筹Phase D → 合理吗？）
2. 信号序列是否合理（有无因果倒置、关键事件缺失）
3. 量价数据是否支撑判定（吸筹+供需评分-40 → 矛盾）
4. 建议是否与判定匹配（ACC-B就给强烈买入 → 过于激进）
5. 时间线合理性（Phase B只5天就进Phase C → 因不充分）

# 输出严格JSON
{
  "consistency_result": "CONSISTENT/INCONSISTENT/PARTIALLY_CONSISTENT",
  "contradictions_found": [
    {"type": "MTF_CONFLICT/SEQUENCE_ERROR/SCORE_MISMATCH/ADVICE_MISMATCH/TIMELINE_ERROR",
     "description": "...", "severity": "CRITICAL/MAJOR/MINOR", "suggestion": "..."}
  ],
  "narrative_coherence_score": 0-100,
  "rewrite_suggestion": "你会怎么讲这个故事？（2-3句话）"
}
```

**调用时机**：每日收盘全量分析后、阶段转移时、建议生成前（最终门控）、反面积分变化超15分。

#### 2.4.4 证伪结果聚合器

```python
class FalsificationAggregator:
    """聚合三层证伪结果，更新系统状态。"""
    
    def process_results(self, stock_code, phase_f, signal_fs, narrative_c):
        adj = {'phase_confidence_delta': 0, 'counter_evidence_delta': 0,
               'signal_adjustments': {}, 'advice_gate': 'PASS', 'alerts': []}
        
        # ── Prompt A结果 ──
        if phase_f and phase_f['falsification_result'] == 'FAILED':
            adj['phase_confidence_delta'] = +5
            adj['counter_evidence_delta'] = -10  # AI认为假设成立，消减反面积分
        elif phase_f and phase_f['falsification_result'] == 'SUCCEEDED':
            adj['phase_confidence_delta'] = -15
            for v in phase_f['violated_conditions']:
                delta = {'CRITICAL': 25, 'MAJOR': 15, 'MINOR': 5}[v['severity']]
                adj['counter_evidence_delta'] += delta
                if v['severity'] == 'CRITICAL':
                    adj['alerts'].append({
                        'level': 'CRITICAL', 'source': 'AI_PHASE_FALSIFICATION',
                        'message': f"AI证伪发现严重矛盾：{v['condition']}"
                    })
            alt = phase_f.get('alternative_hypothesis', {})
            if alt.get('confidence', 0) >= 70:
                adj['alerts'].append({
                    'level': 'WARNING', 'source': 'AI_ALTERNATIVE',
                    'message': f"AI认为真实阶段可能是{alt['phase']}（{alt['confidence']}%）"
                })
        elif phase_f and phase_f['falsification_result'] == 'PARTIAL':
            adj['phase_confidence_delta'] = -5
            adj['counter_evidence_delta'] += 8
        
        # ── Prompt B结果 ──
        for sig_type, sf in signal_fs.items():
            if sf['falsification_result'] == 'FALSE':
                adj['signal_adjustments'][sig_type] = {
                    'action': 'INVALIDATE',
                    'new_likelihood': max(0.1, sf.get('original_likelihood', 0.5) * 0.3),
                }
                if sig_type in ('Spring', 'JOC', 'BreakIce', 'LPSY'):
                    adj['advice_gate'] = 'BLOCK'  # 关键入场信号被证伪→阻止建议
            elif sf['falsification_result'] == 'SUSPECT':
                adj['signal_adjustments'][sig_type] = {
                    'action': 'DOWNGRADE',
                    'new_likelihood': sf.get('original_likelihood', 0.5) * 0.7,
                }
                if sig_type in ('Spring', 'JOC'):
                    adj['advice_gate'] = max(adj['advice_gate'], 'DOWNGRADE')
            elif sf['falsification_result'] == 'GENUINE':
                adj['signal_adjustments'][sig_type] = {
                    'action': 'CONFIRM',
                    'new_likelihood': min(0.95, sf.get('original_likelihood', 0.5) * 1.1),
                }
        
        # ── Prompt C结果 ──
        if narrative_c and narrative_c['consistency_result'] == 'INCONSISTENT':
            for c in narrative_c['contradictions_found']:
                if c['severity'] == 'CRITICAL':
                    adj['advice_gate'] = 'BLOCK'
                elif c['severity'] == 'MAJOR' and adj['advice_gate'] == 'PASS':
                    adj['advice_gate'] = 'DOWNGRADE'
        
        return adj
        # BLOCK: 禁止买入/卖出建议，仅WAIT
        # DOWNGRADE: 建议降一级（STRONG_BUY→BUY, BUY→WATCH等）
        # PASS: 正常生成
```

#### 2.4.5 证伪硬化机制

```python
class FalsificationScheduler:
    """连续3次证伪失败→冷却30日（防止浪费API token）。但ORANGE_ALERT/用户手动可绕过。"""
    def should_falsify(self, stock_code, trigger_type) -> bool:
        recent_3 = self.history.get(stock_code, [])[-3:]
        if len(recent_3) == 3 and all(r == 'FAILED' for r in recent_3):
            if trading_days_since(self.last_date[stock_code]) < 30:
                return trigger_type in ('ORANGE_ALERT', 'USER_MANUAL', 'PHASE_TRANSITION')
        return True
```

### 2.5 L4: AI投资建议生成器

建议生成是最终输出层，融合L1量化评分 + L2-F证伪结果。

```python
class AIAdvisor:
    def generate_advice(self, stock_code, quant_scores, falsification_adj, user_context):
        # 门控检查
        if falsification_adj['advice_gate'] == 'BLOCK':
            return {'advice_type': 'WAIT', 'reasoning': '证伪检验未通过，暂不生成建议',
                    'alerts': falsification_adj['alerts']}
        
        prompt = f"""基于以下分析结果，为{stock_code}生成最终投资建议。

## 量化评分
- 大盘共振: {quant_scores.market_alignment}/30
- 阶段得分: {quant_scores.phase_score}/25
- 信号链完成度: {quant_scores.chain_score}/20
- 多时间框架共振: {quant_scores.mtf_score}/15
- 供需评分: {quant_scores.sd_score}/10
- 总分: {quant_scores.total}/100

## 九大买入检验
{format_nine_tests(quant_scores.nine_tests)}
通过: {quant_scores.nine_tests_passed}/9

## 阶段假设健康度
- 反面证据积分: {quant_scores.counter_score}/100（{quant_scores.alert_level}）
- AI证伪结果: {falsification_adj.get('phase_falsification_summary', '未执行')}
- 距紧急反转阈值: {71 - quant_scores.counter_score}分

## 用户持仓
- 持有: {user_context.holding}, 成本: {user_context.cost_price}

## 输出严格JSON
{{"advice_type": "STRONG_BUY|BUY|WATCH|HOLD|REDUCE|SELL|STRONG_SELL|WAIT",
  "confidence": 0-100, "summary": "一句话", "reasoning": "3-5句话引用数据",
  "trade_plan": {{"entry_price":..., "stop_loss":..., "target_1":..., "target_2":...,
                  "position_pct":..., "rr_ratio":...}},
  "key_watch_points": ["..."], "invalidation": "...", "valid_until": "N交易日"}}"""
        
        response = call_llm([{"role": "user", "content": prompt}])
        advice = parse_json(response)
        
        # 门控降级
        if falsification_adj['advice_gate'] == 'DOWNGRADE':
            advice = downgrade_advice(advice)
        
        return advice
```

---

## 第三部分：FSM紧急反转路径（V3.1新增）

### 3.1 问题论证

**当前FSM的缺陷拓扑**：

```
MKD ──→ ACC-A ──→ ACC-B ──→ ACC-C ──→ ACC-D ──→ MKU
                    ↑          │
                    └──────────┘  (唯一回退: ACC-C → ACC-B)

问题：没有任何路径从 ACC-* 跳转到 DIS-* 或 MKD
```

**书中直接证据**：
- 派发案例：看似吸筹的区间（SC→AR→ST完整），但SOW+UT+反弹无需求三个反面证据推翻判断。书中原话核心意思：如果你在此区间做多了，看到这些，必须离场避免灾难。
- Spring失败：Spring后价格未迅速收回支撑上方+成交量持续放大 → 这不是Spring，而是有效突破。
- 再吸筹vs再派发：出现SOW或带量UT → 这个震荡区是派发。

### 3.2 反面证据积分机制

为每只处于阶段假设中的股票维护 `counter_evidence_score`（0-100）：

#### 吸筹假设下的反面证据

| 事件 | 积分 | 条件 | 书中逻辑 |
|------|------|------|---------|
| Spring失败（3日未收回支撑） | +25 | ACC-C | "不是真正的Spring，是有效突破" |
| Spring失败放量加重 | +15 | 叠加上条 | "成交量持续放大"→供应扩大 |
| SOW出现 | +30 | ACC-B/C | "供应控制市场"的直接证据 |
| 反弹无需求（连续2次缩量递减） | +20 | ACC-B/C | "回升过程缺乏需求加入" |
| UT出现 | +15 | ACC-B/C | 吸筹区出现UT=CM出货信号 |
| 量价特征逆转（跌波量>涨波量，20日） | +20 | 任何ACC | "下降的量和蜡烛大于上升的，这是派发" |
| SC低点被有效跌破（5日未收回） | +35 | 任何ACC | SC低点是吸筹假设根基 |
| 北向资金持续流出（连续10日） | +10 | A股适配 | CM代理指标看空 |

#### 正面证据消减

| 事件 | 消减 |
|------|------|
| 成功缩量ST | -15 |
| SOS出现 | -25 |
| Spring成功确认 | -30 |
| VDB出现 | -10 |

#### 积分阈值

| 范围 | 行为 |
|------|------|
| 0-30 | 正常 |
| 31-50 | **黄色警报**：标注"假设受到质疑"，暂停新建仓 |
| 51-70 | **橙色警报**：暂停买入建议，已有建议标记失效 |
| 71-100 | **红色 → 触发紧急反转** |

**积分衰减**：每交易日自然衰减0.5分，防止远古证据永久累积。

### 3.3 紧急反转状态转移

积分≥71时：

```python
def emergency_reversal(stock_code, current_phase, counter_score, evidence_list):
    has_sow = any(e.type == 'SOW' for e in evidence_list)
    has_break_new_low = any(e.type == 'NEW_LOW_BREAK' for e in evidence_list)
    has_ut = any(e.type == 'UT' for e in evidence_list)
    
    if has_break_new_low:
        # 情况A: SC低点被有效跌破 → 回到下跌趋势
        return 'MKD', "SC低点被有效跌破，震荡区为下跌中继而非吸筹底部"
    elif has_sow and supply_dominant(evidence_list):
        # 情况B: SOW+供应主导 → 震荡区性质是派发
        return 'DIS-D', "SOW+供应主导，原吸筹假设被推翻，真实性质为派发"
    elif has_ut and not has_sow:
        # 情况C: 有UT但未出现SOW → 派发中期
        return 'DIS-B', "出现UT+反弹无需求，可能是派发主体阶段"
    else:
        # 情况D: 方向不明确 → 中性待判定
        return 'TR_UNDETERMINED', "反面证据累积但方向不够明确"
    
    # 级联风控动作：
    invalidate_all_buy_advice(stock_code)
    trigger_stop_loss_review(stock_code)
    push_critical_alert(stock_code, current_phase, new_phase, reasoning)
```

### 3.4 修正后的完整FSM

```
                   ┌──────── 紧急反转(≥71分) ────────┐
                   │                                 │
                   ▼                                 │
    ┌──── TR_UNDETERMINED ◄──┐                       │
    │      (中性待判定)       │                       │
    │  SOS/Spring → ACC方向   │                       │
    │  SOW/UT → DIS方向      │                       │
    │                        │                       │
    ▼                        │                       │
MKD → ACC-A → ACC-B → ACC-C ─┼─→ ACC-D → ACC-E/MKU
                ↑        │   │
                └────────┘   │    紧急反转可从任何ACC-*触发
               (正常回退)     │
                             ├── 情况A(SC破位) → MKD
                             ├── 情况B(SOW+供应) → DIS-D
                             ├── 情况C(UT) → DIS-B
                             └── 情况D(不明确) → TR_UNDETERMINED

对称：DIS-* 同样有紧急反转路径 → ACC-* 或 TR_UNDETERMINED
```

### 3.5 TR_UNDETERMINED状态

```python
class TRUndetermined:
    """方向不明时的中性等待状态。对应书中'避免在震荡区内交易，等待右手边明确信号'。"""
    exit_to_acc = ['Spring确认', 'SOS出现', '终极震仓后强反弹']
    exit_to_dis = ['SOW出现', '破冰', 'UTAD确认']
    restrictions = {'buy': False, 'sell': False, 'allowed': 'WAIT_ONLY'}
```

### 3.6 与证伪引擎的集成

**关键集成点**：AI证伪发现的CRITICAL级矛盾直接给反面积分加25分 → 可触发黄→橙→红级联 → 最终触发紧急反转。

```python
class PhaseFSM:
    def process_bar(self, stock_code, new_bar, context, signals):
        current = self.get_current_phase(stock_code)
        
        # 1. 规则引擎层面的反面证据更新
        ce_result = self.counter_tracker.update(stock_code, hypothesis, new_bar, context, signals)
        
        # 2. AI证伪结果的反面证据追加（如果当日有执行证伪）
        if today_falsification_result:
            ce_result.score += today_falsification_result['counter_evidence_delta']
        
        # 3. 检查是否触发紧急反转
        if ce_result['reversal_triggered']:
            self.force_transition(stock_code, current, ce_result['reversal_target'])
            return ce_result
        
        # 4. 正常状态转移逻辑（不变）
        # ...
```

---

## 第四部分：补全的策略组件

### 4.1 九大买入检验

```python
class NineBuyingTests:
    def evaluate(self, stock, context, thresholds):
        results = {}
        results['T1'] = {'name': '下跌目标已达到', 'passed': stock.low <= context.pf_target * 1.02}
        results['T2'] = {'name': 'PS→SC→AR→ST序列完成', 'passed': context.has_stopping_sequence}
        results['T3'] = {'name': '看涨量价（反弹放量回调缩量）', 'passed': context.up_vol > context.down_vol}
        results['T4'] = {'name': '支撑位确立（多次测试不破）', 'passed': context.support_tests >= 2}
        results['T5'] = {'name': '供应枯竭（低量测试）', 'passed': context.last_test_vol < thresholds['low_vol_threshold']}
        results['T6'] = {'name': '个股强于大盘', 'passed': context.relative_strength > 1.0}
        results['T7'] = {'name': 'Spring/震仓已确认', 'passed': context.spring_confirmed or context.shakeout_confirmed}
        results['T8'] = {'name': '趋势线突破或SOS出现', 'passed': context.downtrend_broken or context.sos_detected}
        results['T9'] = {'name': '因果充分（TR≥30日）', 'passed': context.tr_duration >= 30}
        passed = sum(1 for r in results.values() if r['passed'])
        return results, passed
```

### 4.2 供需评分公式

```python
class SupplyDemandScore:
    """六维度加权：-100(极端供应) 到 +100(极端需求)"""
    def calculate(self, stock, context):
        scores = {
            'volume_price': vp_balance(context) * 100,     # 权重0.30
            'bar_pattern': bar_bull_ratio(context) * 200,   # 权重0.20
            'trend_position': channel_position(context),    # 权重0.15
            'smart_money': context.north_flow_normalized,   # 权重0.15
            'weis_wave': context.weis_balance,              # 权重0.10
            'stopping': stopping_score(context),            # 权重0.10
        }
        weights = [0.30, 0.20, 0.15, 0.15, 0.10, 0.10]
        return round(sum(s*w for s,w in zip(scores.values(), weights)), 1)
```

### 4.3 维斯波

```python
class WeisWave:
    """将连续同向K线聚合为波，累计波量，对比多空力量。"""
    def calculate(self, bars, min_reversal_pct=0.02):
        waves = []  # [{'direction':'UP/DOWN', 'volume':int, 'bars':int, 'price_change':float}]
        # 遍历K线，方向改变时（反向超过min_reversal_pct）切换波
        # ...（完整实现见V3.0文档）
        return waves
    
    def analyze_balance(self, waves, recent_n=6):
        up = [w for w in waves[-recent_n:] if w['direction'] == 'UP']
        down = [w for w in waves[-recent_n:] if w['direction'] == 'DOWN']
        avg_up = sum(w['volume'] for w in up) / max(len(up), 1)
        avg_down = sum(w['volume'] for w in down) / max(len(down), 1)
        return round((avg_up - avg_down) / (avg_up + avg_down + 1e-9) * 100, 1)
```

---

## 第五部分：完整系统架构与开发规范

### 5.1 项目结构

```
wyckoffpro/
├── main.py
├── config/
│   ├── default.yaml
│   ├── presets/
│   └── watchlist.json
├── data/
│   ├── collector.py            # M1: 数据采集
│   ├── storage.py              # SQLite存储
│   ├── cleaner.py              # 数据清洗
│   └── schema.sql
├── engine/
│   ├── thresholds.py           # 自适应阈值
│   ├── phase_fsm.py            # M2: 阶段FSM（含紧急反转）
│   ├── counter_evidence.py     # V3.1: 反面证据追踪器
│   ├── signal_detector.py      # M3: 13种信号似然度
│   ├── signal_chain.py         # 复合信号链追踪
│   ├── nine_tests.py           # 九大检验
│   ├── supply_demand.py        # 供需评分
│   ├── weis_wave.py            # 维斯波
│   ├── pnf_chart.py            # M10: 点数图
│   ├── channel.py              # 趋势通道+超买超卖线
│   └── mtf_analyzer.py         # 多时间框架
├── ai/
│   ├── llm_client.py           # LLM调用封装
│   ├── falsification_engine.py # V3.1: 证伪引擎（A+B+C三层）
│   ├── falsification_aggregator.py # V3.1: 证伪结果聚合
│   ├── falsification_scheduler.py  # V3.1: 硬化/冷却调度
│   ├── advisor.py              # L4: 投资建议生成
│   └── prompts/
│       ├── phase_falsification.md   # Prompt A模板
│       ├── signal_falsification.md  # Prompt B模板
│       ├── signal_checklists/       # 各信号专用证伪清单
│       │   ├── spring.md
│       │   ├── sc.md
│       │   ├── joc.md
│       │   └── sow.md
│       ├── narrative_consistency.md # Prompt C模板
│       └── advice_generation.md     # L4建议模板
├── trade/
│   ├── plan_generator.py
│   ├── risk_manager.py
│   └── position_tracker.py
├── backtest/
│   ├── engine.py
│   ├── metrics.py
│   └── optimizer.py
├── ui/
│   ├── app.py
│   ├── pages/
│   │   ├── dashboard.py
│   │   ├── scanner.py
│   │   ├── analysis.py
│   │   ├── plans.py
│   │   ├── backtest.py
│   │   └── settings.py
│   └── components/
│       ├── kline_chart.py
│       ├── pnf_chart.py
│       ├── signal_panel.py
│       ├── advice_card.py
│       ├── counter_evidence_bar.py  # V3.1: 反面积分仪表盘
│       └── phase_bar.py
├── tests/
│   ├── test_signals.py
│   ├── test_phase_fsm.py
│   ├── test_emergency_reversal.py   # V3.1: 紧急反转测试
│   ├── test_falsification.py        # V3.1: 证伪引擎测试
│   └── fixtures/
├── requirements.txt
└── README.md
```

### 5.2 SQLite Schema（含V3.1新增表）

```sql
-- 日K线数据
CREATE TABLE kline_daily (
    stock_code TEXT NOT NULL, trade_date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER, amount REAL, turnover_rate REAL, pct_change REAL, amplitude REAL,
    PRIMARY KEY (stock_code, trade_date)
);

-- 威科夫阶段
CREATE TABLE wyckoff_phase (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL, phase_code TEXT NOT NULL,
    start_date TEXT NOT NULL, end_date TEXT,
    confidence REAL, tr_upper REAL, tr_lower REAL,
    ice_line REAL, creek_line REAL,
    timeframe TEXT DEFAULT 'daily',
    UNIQUE(stock_code, start_date, timeframe)
);

-- 威科夫信号
CREATE TABLE wyckoff_signal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL, signal_date TEXT NOT NULL, signal_type TEXT NOT NULL,
    likelihood REAL NOT NULL, strength INTEGER, phase_code TEXT,
    trigger_price REAL, trigger_volume INTEGER,
    is_confirmed INTEGER DEFAULT 0, confirm_date TEXT,
    ai_falsification_result TEXT,  -- V3.1: GENUINE/SUSPECT/FALSE/NULL
    ai_reasoning TEXT, rule_detail TEXT, timeframe TEXT DEFAULT 'daily'
);

-- 信号链追踪
CREATE TABLE signal_chain (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL, chain_type TEXT NOT NULL,
    start_date TEXT NOT NULL, events TEXT NOT NULL,
    completion_pct INTEGER, status TEXT DEFAULT 'ACTIVE',
    timeframe TEXT DEFAULT 'daily'
);

-- V3.1新增：反面证据追踪
CREATE TABLE counter_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    hypothesis TEXT NOT NULL,        -- ACCUMULATION / DISTRIBUTION
    current_score INTEGER DEFAULT 0,
    alert_level TEXT DEFAULT 'NONE', -- NONE/YELLOW/ORANGE/RED
    events TEXT,                     -- JSON: 事件列表
    created_at TEXT, last_updated TEXT,
    is_active INTEGER DEFAULT 1
);

-- V3.1新增：证伪记录
CREATE TABLE falsification_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    falsification_type TEXT NOT NULL, -- PHASE/SIGNAL/NARRATIVE
    executed_at TEXT NOT NULL,
    result TEXT NOT NULL,             -- FAILED/SUCCEEDED/PARTIAL (or GENUINE/SUSPECT/FALSE)
    detail TEXT,                      -- JSON: 完整的LLM输出
    adjustments_applied TEXT,         -- JSON: 应用的调整（积分变化/似然度修正/门控结果）
    token_used INTEGER               -- 本次消耗的token数
);

-- 投资建议
CREATE TABLE advice (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL, created_at TEXT NOT NULL,
    advice_type TEXT NOT NULL, confidence REAL,
    summary TEXT, reasoning TEXT,
    trade_plan TEXT, key_watch_points TEXT,
    invalidation TEXT, valid_until TEXT,
    quant_score REAL, nine_tests_passed INTEGER,
    counter_evidence_score INTEGER,   -- V3.1: 生成时的反面积分
    falsification_gate TEXT,          -- V3.1: PASS/DOWNGRADE/BLOCK
    is_expired INTEGER DEFAULT 0
);

-- 交易计划
CREATE TABLE trade_plan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL, direction TEXT NOT NULL,
    entry_mode TEXT, entry_price REAL, stop_loss REAL,
    target_1 REAL, target_2 REAL, rr_ratio REAL, position_pct REAL,
    status TEXT DEFAULT 'DRAFT', linked_advice_id INTEGER, created_at TEXT, notes TEXT
);

-- 自选股
CREATE TABLE watchlist (
    stock_code TEXT NOT NULL, group_name TEXT DEFAULT 'default',
    added_at TEXT, notes TEXT, PRIMARY KEY(stock_code, group_name)
);
```

### 5.3 配置文件 default.yaml（含V3.1新增项）

```yaml
data:
  source: tushare
  tushare_token: ""
  history_years: 5
  update_schedule: "15:30"

thresholds:
  climax_vol_percentile: 95
  climax_range_percentile: 95
  spring_max_penetration_atr: 1.5
  st_vol_ratio: 0.60
  tr_min_duration: 20
  tr_max_amplitude: 0.25
  joc_vol_percentile: 85
  sot_shrink_ratio: 0.50
  evr_vol_multiplier: 1.5
  dead_corner_min_bars: 8
  dead_corner_range_ratio: 0.40
  adaptive_lookback: 120
  adaptive_enabled: true

phase_fsm:
  min_evidence_for_transition: 2
  anomaly_transition_alert: true

# V3.1新增
emergency_reversal:
  enabled: true
  spring_fail_recovery_bars: 3
  spring_fail_vol_multiplier: 1.5
  new_extreme_confirm_bars: 5
  weak_rally_consecutive: 2
  yellow_alert_threshold: 31
  orange_alert_threshold: 51
  red_reversal_threshold: 71
  score_decay_per_day: 0.5
  score_max: 100

signals:
  min_likelihood_to_record: 0.30
  min_likelihood_for_alert: 0.60
  ambiguity_threshold: 0.15
  chain_watch_threshold: 60
  chain_advice_threshold: 85

nine_tests:
  min_pass_for_buy: 7
  min_pass_for_watch: 5

risk:
  max_single_risk_pct: 2.0
  max_total_risk_pct: 10.0
  min_rr_ratio: 3.0
  t1_overnight_premium: 0.005

ai:
  enabled: true
  api_provider: anthropic
  model: claude-sonnet-4-20250514
  max_tokens: 2000
  daily_token_budget: 200000
  # V3.1: 证伪引擎配置
  falsification:
    enabled: true
    prompt_a_enabled: true    # 阶段证伪
    prompt_b_enabled: true    # 信号证伪
    prompt_c_enabled: true    # 叙事一致性
    hardening_consecutive: 3  # 连续N次证伪失败后冷却
    hardening_cooldown_days: 30
    # 信号证伪的触发条件
    signal_falsify_min_likelihood: 0.50
    signal_falsify_critical_types: ["Spring", "JOC", "BreakIce", "LPSY"]

ui:
  theme: dark
  default_period: daily
  chart_style: candle
  alert_sound: true

a_share_adapt:
  enabled: true
  limit_up_as_bc: true
  limit_down_as_sc: true
  north_flow_weight: 0.15
  chip_data_enabled: false
  t1_entry_delay: true
```

### 5.4 每日分析完整流程（V3.1）

```python
async def daily_analysis_pipeline(stock_code):
    """每日收盘后对每只自选股执行的完整分析流程"""
    
    # ── L1: 规则引擎计算 ──
    klines = data_store.get_klines(stock_code, 'daily', 120)
    thresholds = adaptive_thresholds.calc(klines)
    phase = phase_fsm.get_current(stock_code)
    signals = signal_detector.scan(klines[-1], phase, thresholds)
    chain = signal_chain.update(stock_code, signals)
    sd_score = supply_demand.calculate(klines, context)
    
    # ── L1: 反面证据积分更新（规则引擎层面） ──
    ce_result = counter_evidence.update(
        stock_code, phase.hypothesis, klines[-1], context, signals
    )
    
    # ── L2-F Prompt B: 关键信号证伪 ──
    signal_falsifications = {}
    for sig in signals:
        if sig.likelihood >= 0.50 or sig.type in CRITICAL_TYPES:
            if falsification_scheduler.should_falsify(stock_code, 'DAILY'):
                sf = await falsification_engine.falsify_signal(sig, klines, phase, context)
                signal_falsifications[sig.type] = sf
    
    # ── L2-F Prompt A: 阶段证伪（条件触发） ──
    phase_falsification = None
    if should_run_phase_falsification(phase, ce_result):
        phase_falsification = await falsification_engine.falsify_phase(
            stock_code, phase, klines, context
        )
        falsification_scheduler.record(stock_code, phase_falsification['falsification_result'])
    
    # ── L2-F Prompt C: 叙事一致性检验 ──
    narrative_check = await falsification_engine.check_narrative(
        stock_code, phase, chain, sd_score, signals, ce_result
    )
    
    # ── 聚合证伪结果 ──
    adjustments = falsification_aggregator.process_results(
        stock_code, phase_falsification, signal_falsifications, narrative_check
    )
    
    # ── 应用调整 ──
    phase_fsm.adjust_confidence(stock_code, adjustments['phase_confidence_delta'])
    counter_evidence.adjust_score(stock_code, adjustments['counter_evidence_delta'])
    for sig_type, adj in adjustments['signal_adjustments'].items():
        signal_store.update_likelihood(stock_code, sig_type, adj['new_likelihood'])
    
    # ── 检查紧急反转（反面积分可能被AI证伪进一步推高） ──
    if counter_evidence.get_score(stock_code) >= config.emergency_reversal.red_reversal_threshold:
        emergency_reversal(stock_code, phase, counter_evidence.get_events(stock_code))
    
    # ── L4: 生成投资建议 ──
    advice = await advisor.generate_advice(
        stock_code, quant_scores, adjustments, user_context
    )
    
    # ── 推送告警 ──
    for alert in adjustments['alerts']:
        alert_manager.push(alert)
    
    return advice
```

### 5.5 开发里程碑（更新）

```
Phase 1 (W1-W6): 核心引擎 + 证伪式AI
  W1: M1数据采集 + SQLite + 数据清洗
  W2: engine/thresholds.py + engine/weis_wave.py + engine/supply_demand.py
  W3: engine/signal_detector.py (13种信号似然度) + engine/phase_fsm.py + engine/counter_evidence.py
  W4: engine/signal_chain.py + engine/nine_tests.py + engine/channel.py
  W5: ai/falsification_engine.py (Prompt A+B+C) + ai/falsification_aggregator.py + ai/advisor.py
  W6: ui/dashboard.py (K线图+阶段色带+信号标记+反面积分仪表盘+建议卡片) 联调

Phase 2 (W7-W10): 交易计划 + 点数图 + 多时间框架
  W7: engine/pnf_chart.py + engine/mtf_analyzer.py
  W8: trade/plan_generator.py + trade/risk_manager.py
  W9: ui/scanner.py + ui/analysis.py + ui/plans.py
  W10: A股适配层 + 全系统联调

Phase 3 (W11-W14): 回测 + 优化
  W11-W12: backtest/engine.py + backtest/metrics.py
  W13: backtest/optimizer.py + 证伪引擎参数调优
  W14: 全面测试 + 文档 + 性能优化
```

### 5.6 技术栈

```
requirements.txt:
  python>=3.11
  pandas>=2.0
  numpy>=1.24
  ta-lib
  tushare>=1.2.89
  akshare>=1.10
  anthropic>=0.25
  streamlit>=1.30
  streamlit-lightweight-charts>=0.8
  plotly>=5.18
  lightgbm>=4.0
  scikit-learn>=1.3
  pyyaml>=6.0
  schedule>=1.2
  loguru>=0.7
```

### 5.7 API Token消耗估算（V3.1）

| 层级 | 场景 | 频率（20只自选股/日） | 单次Token | 日均Token |
|------|------|---------------------|-----------|----------|
| Prompt B（信号证伪） | 每股1-2个关键信号 | ~30次 | ~1200 | ~36,000 |
| Prompt A（阶段证伪） | ~30%的股票触发 | ~6次 | ~1500 | ~9,000 |
| Prompt C（叙事一致性） | 每股1次 | 20次 | ~1000 | ~20,000 |
| L4（建议生成） | 门控通过的股票 | ~15次 | ~1200 | ~18,000 |
| **日均总计** | | **~71次** | | **~83,000** |

---

## 第六部分：AI开发专用指令

### 6.1 项目初始化

```
请开发Python项目wyckoffpro，技术栈：Python 3.11+, Streamlit, Pandas, NumPy, SQLite, deepseek API。
个人自用A股量价分析工具，核心理论是孟洪涛版威科夫操盘法。
系统通过量价数据自动识别威科夫四阶段，检测13种信号，
通过证伪式AI架构（阶段证伪/信号证伪/叙事一致性检验）校验判定结果，
结合反面证据积分和紧急反转机制确保假设可推翻，最终生成投资建议。
按上述项目结构创建目录和文件。
```

### 6.2 关键模块开发指令

**开发engine/counter_evidence.py时**：
```
实现CounterEvidenceTracker类。为每只股票维护反面证据积分(0-100)。
每根新K线到来时检查8种吸筹反面事件（Spring失败+25、SOW+30、SC破位+35等），
4种正面消减（成功ST-15、SOS-25等），每日衰减0.5分。
积分31-50黄色警报，51-70橙色，≥71触发emergency_reversal()。
详见本文档第三部分反面证据积分表。
```

**开发ai/falsification_engine.py时**：
```
实现三个证伪Prompt（A阶段/B信号/C叙事一致性）。
核心理念：LLM的角色是"唱反调"，尝试推翻FSM的判定。
Prompt B需要根据signal_type动态注入对应的证伪检查清单（Spring7条/SC5条/JOC5条/SOW4条）。
输出严格JSON，结果通过FalsificationAggregator驱动反面积分和建议门控。
详见本文档2.4节完整Prompt模板。
```

---

*本文档为WyckoffPro系统V3.1合并终稿。涵盖：策略审查修正(S01-S09)、证伪式AI架构(三层Prompt)、FSM紧急反转路径(反面证据积分+假设推翻)、补全策略组件(九大检验/供需公式/维斯波)、完整项目结构和开发规范。可直接用于指导AI进行模块化开发。*
