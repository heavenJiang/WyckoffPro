基于以下分析结果，为{stock_code}生成最终投资建议。

## 量化评分
- 大盘共振: {market_alignment}/30
- 阶段得分: {phase_score}/25
- 信号链完成度: {chain_score}/20
- 多时间框架共振: {mtf_score}/15
- 供需评分: {sd_score}/10
- 总分: {total_score}/100

## 九大买入检验
{nine_tests_detail}
通过: {nine_tests_passed}/9

## 阶段假设健康度
- 当前阶段: {phase_code}（{phase_name}）
- 阶段置信度: {phase_confidence}%
- 反面证据积分: {counter_score}/100（{alert_level}）
- AI证伪结果: {falsification_summary}
- 距紧急反转阈值: 还剩{to_reversal}分

## 关键价位
- 支撑: {support_1} / {support_2}
- 阻力: {resistance_1} / {resistance_2}
- 止损参考: {stop_loss_ref}
- 目标价: {target_1} / {target_2}（P&F目标: {pnf_target}）

## 用户持仓
- 持有: {holding_status}
- 成本: {cost_price}
- 当前浮盈: {unrealized_pnl}

## 输出严格JSON
```json
{
  "advice_type": "STRONG_BUY或BUY或WATCH或HOLD或REDUCE或SELL或STRONG_SELL或WAIT",
  "confidence": 0-100,
  "summary": "一句话核心观点",
  "reasoning": "3-5句话，引用具体数据支撑",
  "trade_plan": {
    "entry_price": 0.0,
    "entry_mode": "限价/市价/突破确认",
    "stop_loss": 0.0,
    "target_1": 0.0,
    "target_2": 0.0,
    "position_pct": 0-100,
    "rr_ratio": 0.0
  },
  "key_watch_points": ["关注点1", "关注点2", "关注点3"],
  "invalidation": "建议失效条件（价格/信号）",
  "valid_until": "N个交易日"
}
```

# 关键规则
- advice_type必须与阶段判定逻辑一致（吸筹早期不给STRONG_BUY）
- 止损必须严格（止损位 = SC低点或Spring低点下方ATR的0.5倍）
- 盈亏比必须≥3:1，否则给WATCH而非BUY
- 反面积分≥51（橙色）时，任何BUY建议必须降为WATCH
- 输出必须是严格的JSON，不包含额外文字
