# WyckoffPro V3.0 — AI增强版开发指导文档

> **文档性质**：可直接指导AI（如Claude/Cursor/Copilot）进行代码开发的完整技术规格
> **版本**：V3.0（基于V2.0策略有效性审查 + AI融合优化）
> **日期**：2026-04-04

---

## 第〇章 V2.0策略有效性审查报告

在进入开发之前，先对V2.0中设计的所有策略进行严格的有效性审查。以下审查基于民生证券2025年1月《威科夫技术分析的概率云表达：从主观到量化》量化研报的实证数据，以及孟洪涛原书的逻辑复核。

### 0.1 关键实证发现（来自A股2010-2022回测）

| 发现 | 数据 | 对系统设计的影响 |
|------|------|-----------------|
| 单一威科夫信号的短期胜率很低 | 3日窗口仅8.54%的形态胜率>55% | **不能依赖单一信号做交易决策** |
| 信号序列的累积效应极其显著 | 从1个形态位到6个形态位，最高胜率从60%提升到90% | **必须使用复合信号链，这是威科夫有效性的核心来源** |
| 中长期优于短期 | 30日窗口有19.64%的形态胜率>55%（vs 3日8.54%） | **系统应定位于中线波段（10-30日持仓），而非超短线** |
| 1日收益率胜率普遍<50% | 高频策略博弈已消耗1日收益空间 | **T+1下的A股入场后第一天盈利概率不高，需耐心持仓** |
| 条件概率是提高有效性的关键 | 形态位增加→有效性指数级增长 | **每一个新信号的出现都应更新整个贝叶斯推断链** |

### 0.2 V2.0策略逐项审查

| 策略项 | 有效性判定 | 问题 | V3.0优化方案 |
|--------|----------|------|-------------|
| 12种单一信号检测规则 | ⚠️ 部分有效 | 阈值为静态硬编码，不同市值/行业/波动率的股票差异巨大 | 改为**自适应阈值**：基于个股近60日的ATR、均量、波动率动态计算 |
| 信号强度1-5级评分 | ❌ 有效性不足 | 主观分级，无量化回测支撑 | 改为**贝叶斯概率评分**：基于历史同类信号的后续N日胜率/赔率 |
| 投资建议置信度加权公式 | ⚠️ 待验证 | 各维度权重（0.3/0.3/0.2/0.2）为人工拍定 | 引入**LLM综合研判层**：让AI综合所有量化指标+市场语境做出自然语言推理 |
| FSM状态机阶段约束 | ✅ 有效 | 逻辑上正确，但过于刚性，现实中阶段边界模糊 | 改为**概率状态机**：每个状态有转移概率，允许模糊边界 |
| 因果关系目标价（P&F计数法） | ✅ 有效但需标注 | P&F目标价不是精确终点 | 输出**目标价区间**（保守/中间/激进三级），接近时由LLM分析是否出现停止行为 |
| 多时间框架共振 | ✅ 有效 | 周线/日线方向一致时胜率确实更高 | 保留并强化，新增**LLM对不一致情况的解读** |
| 再吸筹vs再派发判定 | ⚠️ 困难 | 这是威科夫分析中最难量化的部分，纯规则引擎准确率有限 | 这是**LLM最适合发挥的场景**：综合多维度模糊证据做定性判断 |
| 北向资金作为CM代理 | ⚠️ 有限 | 北向资金并非唯一的聪明钱，且有时滞 | 降权为辅助指标（权重10%），加入龙虎榜、大宗交易、融资融券作为补充 |

### 0.3 核心结论

1. **威科夫方法在A股是有效的，但有效性来源于信号序列的累积概率，而非单一信号**
2. **最适合中线波段交易（10-30日），不适合日内或隔日超短**
3. **最难的部分（阶段判定、再吸筹vs再派发、模糊情境解读）恰好是LLM最擅长的**
4. **固定阈值规则在不同个股上表现差异大，需要自适应机制**

---

## 第一章 系统总体架构

### 1.1 架构定位

```
个人自用 · 本地运行 · Python单体 · AI增强
```

### 1.2 技术栈

| 组件 | 方案 | 说明 |
|------|------|------|
| 语言 | Python 3.11+ | 算法+后端统一 |
| Web UI | Streamlit（原型期）→ Dash/Plotly（成熟期） | 快速迭代 |
| K线图表 | lightweight-charts-python（TradingView封装） | 金融图表最优解 |
| 数据库 | SQLite + DuckDB（行情分析加速） | 零运维 |
| 算法 | NumPy + Pandas + TA-Lib | 量化分析标准 |
| ML模型 | LightGBM（阶段分类）+ scipy（统计检验） | 轻量高效 |
| LLM引擎 | Anthropic Claude API（claude-sonnet-4-20250514） | 核心AI层 |
| 数据源 | Tushare Pro（首选）/ AKShare（备选） | A股数据 |
| 配置 | YAML文件 | 人类可读 |
| 调度 | APScheduler | 定时任务 |

### 1.3 模块架构图

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit Web UI                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │
│  │ K线图表   │ │ 信号面板  │ │ 建议卡片  │ │ 回测报告   │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬──────┘ │
└───────┼────────────┼────────────┼──────────────┼────────┘
        │            │            │              │
┌───────┴────────────┴────────────┴──────────────┴────────┐
│                    业务逻辑层                             │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌───────┐ │
│  │M2 阶段 │ │M3 信号 │ │M5 计划 │ │M6 风控 │ │M7回测 │ │
│  │识别引擎│ │检测引擎│ │生成器  │ │管理   │ │引擎  │ │
│  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └──┬────┘ │
└──────┼──────────┼──────────┼──────────┼─────────┼──────┘
       │          │          │          │         │
┌──────┴──────────┴──────────┴──────────┴─────────┴──────┐
│              M11 - AI研判引擎（LLM层）                    │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────┐  │
│  │ 量价语义解读  │ │ 综合研判推理  │ │ 自然语言建议生成│  │
│  └──────────────┘ └──────────────┘ └────────────────┘  │
└────────────────────────┬───────────────────────────────┘
                         │
┌────────────────────────┴───────────────────────────────┐
│                    数据层                                │
│  ┌──────────┐ ┌────────────┐ ┌──────────┐ ┌─────────┐ │
│  │M1 行情   │ │SQLite      │ │M10 点数图│ │M8 配置  │ │
│  │数据采集  │ │数据存储    │ │计算引擎  │ │管理    │ │
│  └──────────┘ └────────────┘ └──────────┘ └─────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## 第二章 M1 - 数据采集模块

### 2.1 数据源接口

```python
# file: wyckoffpro/data/provider.py
from abc import ABC, abstractmethod
import pandas as pd

class DataProvider(ABC):
    """数据源抽象接口，支持替换不同数据源"""
    
    @abstractmethod
    def get_daily_kline(self, code: str, start: str, end: str) -> pd.DataFrame:
        """获取日K线，返回标准DataFrame
        columns: date, open, high, low, close, volume, amount, turnover_rate
        """
        pass
    
    @abstractmethod
    def get_minute_kline(self, code: str, freq: str, start: str, end: str) -> pd.DataFrame:
        """获取分钟K线, freq: '1min','5min','15min','30min','60min'"""
        pass
    
    @abstractmethod
    def get_index_daily(self, code: str, start: str, end: str) -> pd.DataFrame:
        """获取指数日K线"""
        pass
    
    @abstractmethod
    def get_money_flow(self, code: str, start: str, end: str) -> pd.DataFrame:
        """获取资金流向：主力净流入、北向资金等"""
        pass

class TushareProvider(DataProvider):
    """Tushare Pro 实现"""
    def __init__(self, token: str):
        import tushare as ts
        self.pro = ts.pro_api(token)
    # ... 各方法实现
```

### 2.2 数据存储Schema

```sql
-- file: schema.sql

CREATE TABLE IF NOT EXISTS stock_info (
    code TEXT PRIMARY KEY,       -- '000791.SZ'
    name TEXT NOT NULL,
    market TEXT NOT NULL,        -- 'SZ','SH','BJ'
    industry TEXT,
    list_date TEXT,
    is_st INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS daily_kline (
    code TEXT NOT NULL,
    date TEXT NOT NULL,          -- 'YYYY-MM-DD'
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER,             -- 手
    amount REAL,                -- 元
    turnover_rate REAL,         -- %
    pct_change REAL,            -- %
    -- 预计算的自适应指标（每次写入时计算）
    atr_20 REAL,                -- 20日ATR
    vol_ma_20 REAL,             -- 20日均量
    volatility_20 REAL,         -- 20日波动率
    PRIMARY KEY (code, date)
);

CREATE TABLE IF NOT EXISTS wyckoff_phase (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    phase_code TEXT NOT NULL,    -- 'ACC-A','DIS-C','MKU' etc.
    start_date TEXT NOT NULL,
    end_date TEXT,               -- NULL=进行中
    confidence REAL,            -- 0-100
    tr_upper REAL, tr_lower REAL,
    ice_line REAL, creek_line REAL,
    prev_phase_id INTEGER,      -- FSM前序状态
    ml_probs TEXT,              -- JSON: 各阶段概率分布
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS wyckoff_signal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    signal_date TEXT NOT NULL,
    signal_type TEXT NOT NULL,   -- 'SC','Spring','JOC','UT' etc.(13种)
    signal_class INTEGER,       -- Spring的1/2/3类
    -- V3.0: 贝叶斯概率评分替代1-5级主观评分
    bayes_win_rate REAL,        -- 历史同类信号的胜率
    bayes_payoff REAL,          -- 历史同类信号的赔率
    bayes_sample_count INTEGER, -- 统计样本数
    phase_code TEXT,            -- 触发时所处阶段
    trigger_price REAL,
    trigger_volume INTEGER,
    rule_detail TEXT,           -- JSON: 各条件匹配详情
    is_confirmed INTEGER DEFAULT 0,
    confirm_date TEXT,
    -- V3.0: 信号链追踪
    chain_id INTEGER,           -- 所属信号链ID
    chain_position INTEGER,     -- 在链中的序号
    chain_completion REAL       -- 链完成度
);

CREATE TABLE IF NOT EXISTS signal_chain (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    chain_type TEXT NOT NULL,    -- 'ACCUMULATION','DISTRIBUTION'
    start_date TEXT NOT NULL,
    completion REAL DEFAULT 0,  -- 0-100%
    status TEXT DEFAULT 'ACTIVE', -- ACTIVE/COMPLETED/FAILED
    events TEXT                  -- JSON: 已触发的事件列表
);

CREATE TABLE IF NOT EXISTS trade_plan (
    id TEXT PRIMARY KEY,        -- UUID
    code TEXT NOT NULL,
    direction TEXT NOT NULL,    -- 'LONG','SHORT'
    entry_mode TEXT NOT NULL,   -- 'EP-01' to 'EP-06'
    entry_price REAL,
    stop_loss REAL,
    target_1 REAL, target_2 REAL, target_3 REAL,  -- 保守/中间/激进
    risk_reward REAL,
    position_pct REAL,
    status TEXT DEFAULT 'DRAFT',
    ai_reasoning TEXT,          -- LLM生成的推理链
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS ai_advice (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    advice_type TEXT NOT NULL,   -- 'STRONG_BUY'...'WAIT'
    confidence REAL,
    reasoning TEXT,              -- LLM生成的完整推理（中文自然语言）
    market_context TEXT,         -- LLM对大盘环境的解读
    signal_chain_summary TEXT,   -- 信号链状态摘要
    timeframe_analysis TEXT,     -- 多时间框架分析结果
    created_at TEXT,
    expired_at TEXT
);
```

---

## 第三章 M2 - 阶段识别引擎

### 3.1 自适应阈值计算

V2.0的固定阈值在不同个股上表现差异大。V3.0改为基于个股自身统计特征的动态阈值。

```python
# file: wyckoffpro/engine/adaptive_threshold.py
import pandas as pd
import numpy as np

class AdaptiveThreshold:
    """基于个股近期统计特征的自适应阈值计算器"""
    
    def __init__(self, df: pd.DataFrame, lookback: int = 60):
        """
        df: 日K线DataFrame，必须含 close, high, low, volume 列
        lookback: 回看天数
        """
        recent = df.tail(lookback)
        self.atr = self._calc_atr(recent, 20)
        self.avg_volume = recent['volume'].mean()
        self.avg_range = ((recent['high'] - recent['low']) / recent['close']).mean()
        self.volatility = recent['close'].pct_change().std() * np.sqrt(252)
        self.avg_body = (abs(recent['close'] - recent['open']) / recent['close']).mean()
    
    def _calc_atr(self, df, period):
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift(1))
        low_close = abs(df['low'] - df['close'].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(period).mean().iloc[-1]
    
    @property
    def climax_vol_multiple(self) -> float:
        """高潮成交量倍数：波动率高的股票降低要求"""
        base = 2.5
        if self.volatility > 0.6:   # 年化波动率>60%的高波动股
            return base * 0.8        # 降至2.0倍
        return base
    
    @property
    def climax_range_multiple(self) -> float:
        """高潮振幅倍数"""
        return 2.0
    
    @property
    def spring_max_penetration(self) -> float:
        """Spring最大穿透幅度：用ATR的1.5倍替代固定3%"""
        return min(self.atr * 1.5 / self._last_close, 0.05)  # 上限5%
    
    @property
    def st_vol_ratio(self) -> float:
        """二次测试量比阈值"""
        return 0.6
    
    @property
    def joc_vol_multiple(self) -> float:
        """JOC突破量倍数"""
        return 1.8
    
    @property
    def tr_min_days(self) -> int:
        """TR最短天数：大盘股可以更短"""
        if self.avg_volume > 500000:  # 日均50万手以上
            return 15
        return 20
    
    @property
    def tr_max_amplitude(self) -> float:
        """TR最大振幅：高波动股放宽"""
        base = 0.20
        return base * (1 + self.volatility / 0.4)  # 波动率越高，允许振幅越大
```

### 3.2 概率状态机（Probabilistic FSM）

V2.0的FSM过于刚性。V3.0改为概率状态机：每个状态转移带概率权重，允许模糊边界。

```python
# file: wyckoffpro/engine/phase_fsm.py
from dataclasses import dataclass
from typing import Optional
import json

VALID_TRANSITIONS = {
    'MKD':     ['ACC-A', 'MKD-RD'],
    'ACC-A':   ['ACC-B'],
    'ACC-B':   ['ACC-C', 'ACC-B'],    # 可停留在B
    'ACC-C':   ['ACC-D', 'ACC-B'],    # Spring失败可回退
    'ACC-D':   ['ACC-E', 'MKU'],
    'ACC-E':   ['MKU'],
    'MKU':     ['MKU-RA', 'DIS-A'],
    'MKU-RA':  ['MKU', 'DIS-A'],      # 再吸筹恢复 或 转派发
    'DIS-A':   ['DIS-B'],
    'DIS-B':   ['DIS-C', 'DIS-B'],
    'DIS-C':   ['DIS-D', 'DIS-B'],
    'DIS-D':   ['DIS-E', 'MKD'],
    'DIS-E':   ['MKD'],
    'MKD-RD':  ['MKD', 'ACC-A'],      # 再派发继续 或 反转
}

@dataclass
class PhaseState:
    code: str                   # 当前阶段编码
    confidence: float           # 置信度 0-100
    start_date: str
    tr_upper: Optional[float] = None
    tr_lower: Optional[float] = None
    ice_line: Optional[float] = None
    creek_line: Optional[float] = None
    
class PhaseFSM:
    """概率有限状态机"""
    
    def __init__(self, initial_state: PhaseState):
        self.state = initial_state
        self.history = [initial_state]
    
    def try_transition(self, target_code: str, confidence: float, 
                       evidence: dict) -> bool:
        """尝试状态转移
        
        Args:
            target_code: 目标阶段编码
            confidence: 转移置信度
            evidence: 支撑转移的证据 {'signals': [...], 'volume_pattern': ..., ...}
        
        Returns:
            是否成功转移
        """
        # 检查转移合法性
        if target_code not in VALID_TRANSITIONS.get(self.state.code, []):
            return False  # 非法转移
        
        # 置信度阈值：必须>50%才执行转移
        if confidence < 50:
            return False
        
        # 执行转移
        new_state = PhaseState(
            code=target_code,
            confidence=confidence,
            start_date=evidence.get('date', ''),
        )
        self.state = new_state
        self.history.append(new_state)
        return True
    
    def get_transition_candidates(self) -> list[str]:
        """获取当前状态的所有合法转移目标"""
        return VALID_TRANSITIONS.get(self.state.code, [])
```

### 3.3 阶段识别主引擎

```python
# file: wyckoffpro/engine/phase_engine.py

class PhaseEngine:
    """阶段识别主引擎：规则层 + ML层 + FSM约束"""
    
    def __init__(self, config: dict):
        self.config = config
        self.ml_model = None  # LightGBM，延迟加载
    
    def identify_phase(self, code: str, df: pd.DataFrame) -> PhaseState:
        """对单只股票执行阶段识别
        
        核心流程：
        1. 计算自适应阈值
        2. 规则引擎判定候选阶段
        3. ML模型输出各阶段概率
        4. FSM验证转移合法性
        5. 综合输出最终判定
        """
        threshold = AdaptiveThreshold(df)
        
        # Step 1: 趋势判定
        trend = self._detect_trend(df)
        
        # Step 2: TR检测
        tr = self._detect_trading_range(df, threshold)
        
        # Step 3: 规则引擎判定候选
        candidates = self._rule_engine_candidates(df, trend, tr, threshold)
        
        # Step 4: ML概率（如果模型已训练）
        if self.ml_model:
            ml_probs = self._ml_predict(df)
            candidates = self._merge_rule_ml(candidates, ml_probs)
        
        # Step 5: FSM约束过滤
        # ... 取候选中置信度最高且FSM合法的
        
        return best_candidate
    
    def _detect_trend(self, df: pd.DataFrame) -> str:
        """趋势判定：基于均线排列+波峰波谷序列
        
        返回: 'UP', 'DOWN', 'SIDEWAYS'
        """
        close = df['close']
        ma50 = close.rolling(50).mean()
        ma120 = close.rolling(120).mean()
        ma250 = close.rolling(250).mean()
        
        latest = close.iloc[-1]
        
        # 多头排列: close > ma50 > ma120 > ma250
        if latest > ma50.iloc[-1] > ma120.iloc[-1] > ma250.iloc[-1]:
            return 'UP'
        # 空头排列
        if latest < ma50.iloc[-1] < ma120.iloc[-1] < ma250.iloc[-1]:
            return 'DOWN'
        return 'SIDEWAYS'
    
    def _detect_trading_range(self, df, threshold) -> Optional[dict]:
        """震荡区间检测
        
        算法：
        1. 在最近N日内寻找被>=3次触及的高点区域和低点区域
        2. 高低点区域的振幅 <= threshold.tr_max_amplitude
        3. 持续时间 >= threshold.tr_min_days
        
        返回: {'upper': float, 'lower': float, 'start': str, 'days': int} or None
        """
        # 实现: 使用局部极值检测 + 价格聚类
        pass
```

---

## 第四章 M3 - 信号检测引擎

### 4.1 信号检测基类

```python
# file: wyckoffpro/engine/signals/base.py

@dataclass
class SignalResult:
    signal_type: str          # 'SC','Spring','JOC'...
    signal_class: int = 0     # Spring的1/2/3类
    trigger_date: str = ''
    trigger_price: float = 0
    trigger_volume: int = 0
    # V3.0: 贝叶斯评分
    bayes_win_rate: float = 0   # 历史同类信号N日胜率
    bayes_payoff: float = 0     # 历史同类信号N日赔率
    bayes_samples: int = 0      # 统计样本数
    # 规则匹配详情
    rule_matches: dict = None   # 每条规则是否满足
    # 信号链
    chain_position: int = 0     # 在信号链中的位置

class SignalDetector(ABC):
    """信号检测器基类"""
    
    @abstractmethod
    def detect(self, df: pd.DataFrame, phase: PhaseState, 
               threshold: AdaptiveThreshold) -> Optional[SignalResult]:
        pass
```

### 4.2 核心信号实现（13种）

**以下仅展示3个最关键的信号实现逻辑，其余按同样模式开发：**

```python
# file: wyckoffpro/engine/signals/spring.py

class SpringDetector(SignalDetector):
    """弹簧效应检测器"""
    
    def detect(self, df, phase, threshold) -> Optional[SignalResult]:
        # 前置条件：必须在ACC-B或ACC-C阶段，且TR已识别
        if phase.code not in ('ACC-B', 'ACC-C'):
            return None
        if phase.tr_lower is None:
            return None
        
        today = df.iloc[-1]
        support = phase.tr_lower
        
        # 条件1：盘中或收盘价跌破支撑
        penetration = (support - today['low']) / support
        if penetration <= 0:
            return None  # 未跌破
        
        # 条件2：穿透幅度不超过自适应阈值
        if penetration > threshold.spring_max_penetration:
            return None  # 穿透太深，可能是真突破而非Spring
        
        # 条件3：收盘价回到支撑附近或上方
        close_vs_support = (today['close'] - support) / support
        if close_vs_support < -0.01:  # 收盘仍在支撑下方超过1%
            return None
        
        # 分类：基于成交量
        vol_ratio = today['volume'] / threshold.avg_volume
        if vol_ratio <= 0.5:
            signal_class = 1   # 一类：极低量，供应耗尽
        elif vol_ratio <= 1.0:
            signal_class = 2   # 二类：中等量，需ST确认
        else:
            signal_class = 3   # 三类：较高量，需更多确认
        
        return SignalResult(
            signal_type='Spring',
            signal_class=signal_class,
            trigger_date=str(today.name),
            trigger_price=today['low'],
            trigger_volume=today['volume'],
            rule_matches={
                'phase_valid': True,
                'penetration': round(penetration, 4),
                'penetration_max': round(threshold.spring_max_penetration, 4),
                'close_above_support': close_vs_support >= -0.01,
                'volume_ratio': round(vol_ratio, 2),
            }
        )
```

```python
# file: wyckoffpro/engine/signals/effort_vs_result.py

class EvRDetector(SignalDetector):
    """努力与结果背离检测器（放量滞涨/放量滞跌）"""
    
    def detect(self, df, phase, threshold) -> Optional[SignalResult]:
        today = df.iloc[-1]
        recent_5 = df.tail(5)
        recent_20 = df.tail(20)
        
        avg_vol_5 = recent_5['volume'].mean()
        avg_pct_20 = recent_20['pct_change'].abs().mean()
        
        vol_ratio = today['volume'] / avg_vol_5
        pct_ratio = abs(today['pct_change']) / avg_pct_20 if avg_pct_20 > 0 else 1
        
        # 放量滞涨：量是近5日均量的1.5倍以上，但涨幅不到近20日均幅的50%
        if vol_ratio >= 1.5 and today['pct_change'] > 0 and pct_ratio < 0.5:
            return SignalResult(
                signal_type='EvR',
                signal_class=1,  # 1=放量滞涨（看跌）
                trigger_date=str(today.name),
                trigger_price=today['close'],
                trigger_volume=today['volume'],
                rule_matches={
                    'vol_ratio': round(vol_ratio, 2),
                    'pct_ratio': round(pct_ratio, 2),
                    'direction': 'bearish_stall'
                }
            )
        
        # 放量滞跌：量是近5日均量的1.5倍以上，但跌幅不到近20日均幅的50%
        if vol_ratio >= 1.5 and today['pct_change'] < 0 and pct_ratio < 0.5:
            return SignalResult(
                signal_type='EvR',
                signal_class=2,  # 2=放量滞跌（看涨）
                trigger_date=str(today.name),
                trigger_price=today['close'],
                trigger_volume=today['volume'],
                rule_matches={
                    'vol_ratio': round(vol_ratio, 2),
                    'pct_ratio': round(pct_ratio, 2),
                    'direction': 'bullish_stall'
                }
            )
        
        return None
```

```python
# file: wyckoffpro/engine/signals/dead_corner.py

class DeadCornerDetector(SignalDetector):
    """死角形态检测器（V2.0/V3.0新增）"""
    
    def detect(self, df, phase, threshold) -> Optional[SignalResult]:
        if len(df) < 12:
            return None
        
        recent = df.tail(12)
        highs = recent['high'].values
        lows = recent['low'].values
        
        # 检测高点序列递降
        high_diffs = np.diff(highs[-8:])
        highs_descending = np.sum(high_diffs < 0) >= 5  # 8个点中至少5次递降
        
        # 检测低点序列递升
        low_diffs = np.diff(lows[-8:])
        lows_ascending = np.sum(low_diffs > 0) >= 5
        
        if not (highs_descending and lows_ascending):
            return None
        
        # 末端振幅收窄
        last3_range = (recent['high'].tail(3).max() - recent['low'].tail(3).min()) / recent['close'].iloc[-1]
        avg_range = threshold.avg_range
        
        if last3_range > avg_range * 0.4:
            return None  # 还不够收窄
        
        # 成交量萎缩
        vol_trend = recent['volume'].tail(5).mean() / threshold.avg_volume
        
        return SignalResult(
            signal_type='DeadCorner',
            trigger_date=str(recent.index[-1]),
            trigger_price=recent['close'].iloc[-1],
            trigger_volume=int(recent['volume'].iloc[-1]),
            rule_matches={
                'highs_descending': True,
                'lows_ascending': True,
                'range_compression': round(last3_range / avg_range, 2),
                'volume_compression': round(vol_trend, 2),
                'phase_context': phase.code,
            }
        )
```

### 4.3 信号链追踪器

```python
# file: wyckoffpro/engine/signal_chain.py

ACCUMULATION_TEMPLATE = [
    {'event': 'PS',       'required': False, 'completion': 10},
    {'event': 'SC',       'required': True,  'completion': 20},
    {'event': 'AR',       'required': True,  'completion': 30},
    {'event': 'ST',       'required': True,  'completion': 40},
    {'event': 'Spring',   'required': False, 'completion': 60},  # 或Shakeout
    {'event': 'ST_after', 'required': False, 'completion': 70},  # Spring后的ST
    {'event': 'SOS',      'required': True,  'completion': 80},  # 或JOC
    {'event': 'LPS',      'required': True,  'completion': 95},
]

DISTRIBUTION_TEMPLATE = [
    {'event': 'PSY',       'required': False, 'completion': 10},
    {'event': 'BC',        'required': True,  'completion': 20},
    {'event': 'AR',        'required': True,  'completion': 30},
    {'event': 'ST',        'required': True,  'completion': 40},
    {'event': 'UT',        'required': False, 'completion': 60},
    {'event': 'SOW',       'required': True,  'completion': 75},
    {'event': 'ICE_BREAK', 'required': True,  'completion': 85},
    {'event': 'LPSY',      'required': True,  'completion': 95},
]

class SignalChainTracker:
    """信号链追踪器：监控吸筹/派发事件序列的完成度"""
    
    def __init__(self, chain_type: str, code: str):
        self.chain_type = chain_type
        self.code = code
        self.template = (ACCUMULATION_TEMPLATE if chain_type == 'ACCUMULATION' 
                        else DISTRIBUTION_TEMPLATE)
        self.triggered_events = []
        self.completion = 0.0
    
    def feed_signal(self, signal: SignalResult) -> float:
        """输入新信号，更新链完成度
        
        关键逻辑：
        - 信号必须按模板顺序出现（允许跳过非必选项）
        - 每个信号只能触发一次
        - 返回更新后的完成度
        """
        event_name = self._map_signal_to_event(signal)
        if not event_name:
            return self.completion
        
        # 检查是否为模板中的下一个期待事件
        next_idx = len(self.triggered_events)
        for i in range(next_idx, len(self.template)):
            if self.template[i]['event'] == event_name:
                self.triggered_events.append({
                    'event': event_name,
                    'signal': signal,
                    'template_idx': i
                })
                self.completion = self.template[i]['completion']
                break
        
        return self.completion
    
    def _map_signal_to_event(self, signal: SignalResult) -> Optional[str]:
        """将信号类型映射到信号链事件"""
        mapping = {
            'SC': 'SC', 'BC': 'BC', 'Spring': 'Spring',
            'Shakeout': 'Spring',  # 震仓等同于Spring位置
            'SOS': 'SOS', 'JOC': 'SOS',  # JOC是SOS的一种
            'SOW': 'SOW', 'ICE_BREAK': 'ICE_BREAK',
            'UT': 'UT', 'UTAD': 'UT',
        }
        return mapping.get(signal.signal_type)
```

---

## 第五章 M11 - AI研判引擎（LLM层）— V3.0核心新增

### 5.1 设计哲学

AI在本系统中的角色不是替代量化规则引擎，而是承担**量化引擎做不好的事情**：

| 量化引擎擅长 | LLM擅长 |
|-------------|---------|
| 明确阈值的信号检测 | 模糊情境的综合判断 |
| 历史统计回测 | 多维度证据的自然语言推理 |
| 数值计算（目标价、仓位） | 解读为什么这个形态可能有效/无效 |
| 高频重复执行 | 处理异常case（如突发消息冲击后的量价解读） |

### 5.2 LLM调用架构

```python
# file: wyckoffpro/ai/llm_engine.py
import anthropic
import json

class WyckoffLLM:
    """威科夫AI研判引擎"""
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        return """你是一位精通威科夫操盘法（孟洪涛版）的A股量价分析专家。你的任务是基于量化引擎提供的数据，进行综合研判并生成投资建议。

## 你的分析框架

你严格遵循威科夫三大定律：
1. **供求关系定律**：需求>供应=上涨，供应>需求=下跌
2. **因果关系定律**：横有多长竖有多高，没有充分的准备过程（吸筹/派发），不会产生持续的趋势
3. **努力与结果定律**：放量滞涨=供应压制需求；放量滞跌=需求吸收供应

## 你的输出要求

1. 分析推理必须引用具体的量价数据（日期、价格、成交量）
2. 每一个判断都必须说明支撑该判断的威科夫证据
3. 识别当前最大的不确定性是什么，以及什么样的后续行为能消除该不确定性
4. 投资建议必须包含明确的操作方向、入场条件、止损条件
5. 用中文回复，术语使用中英文对照（如"弹簧效应（Spring）"）

## 你的局限性声明

你生成的是基于威科夫量价分析的技术面建议，不构成投资顾问意见。市场存在不可预测的风险。"""

    def analyze_stock(self, context: dict) -> dict:
        """对单只股票进行AI综合研判
        
        Args:
            context: 量化引擎输出的结构化数据，包含：
                - stock_info: 股票基本信息
                - current_phase: 当前阶段识别结果
                - recent_signals: 近期检测到的信号列表
                - signal_chain: 信号链状态
                - kline_summary: 近30日K线摘要统计
                - market_phase: 大盘阶段
                - relative_strength: 个股相对强度
                - support_resistance: 支撑/阻力位列表
                - multi_timeframe: 周线/日线/60分钟阶段
        
        Returns:
            dict with keys: advice_type, confidence, reasoning, 
                           trade_plan, risk_warning
        """
        user_prompt = self._build_analysis_prompt(context)
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        return self._parse_response(response.content[0].text)
    
    def _build_analysis_prompt(self, ctx: dict) -> str:
        return f"""请对以下股票进行威科夫综合研判分析：

## 基本信息
- 股票：{ctx['stock_info']['name']}（{ctx['stock_info']['code']}）
- 行业：{ctx['stock_info']['industry']}

## 量化引擎判定结果
- 当前阶段：{ctx['current_phase']['code']}（置信度{ctx['current_phase']['confidence']:.1f}%）
- 信号链类型：{ctx['signal_chain']['type']}
- 信号链完成度：{ctx['signal_chain']['completion']:.0f}%
- 已触发事件：{json.dumps(ctx['signal_chain']['events'], ensure_ascii=False)}

## 近期信号（最近10个交易日）
{self._format_signals(ctx['recent_signals'])}

## K线统计摘要（近30日）
- 涨跌幅：{ctx['kline_summary']['pct_30d']:.2f}%
- 最高价：{ctx['kline_summary']['high_30d']:.3f}
- 最低价：{ctx['kline_summary']['low_30d']:.3f}
- 日均成交量：{ctx['kline_summary']['avg_vol_30d']:.0f}手
- 成交量趋势：{ctx['kline_summary']['vol_trend']}
- 近5日vs近20日量比：{ctx['kline_summary']['vol_ratio_5_20']:.2f}

## 支撑与阻力
{self._format_sr(ctx['support_resistance'])}

## 多时间框架
- 周线阶段：{ctx['multi_timeframe']['weekly']}
- 日线阶段：{ctx['multi_timeframe']['daily']}
- 60分钟：{ctx['multi_timeframe']['60min']}

## 大盘环境
- 上证指数阶段：{ctx['market_phase']}
- 个股相对强度：{ctx['relative_strength']:.2f}

---

请按以下格式输出你的分析：

### 1. 供需力量研判
（分析当前供需天平倾向哪一方，引用具体量价证据）

### 2. 阶段判定验证
（你是否同意量化引擎的阶段判定？如有不同意见请说明理由）

### 3. 关键不确定性
（当前最大的不确定性是什么？什么后续行为能确认或否定当前判断？）

### 4. 投资建议
- 建议类型：（STRONG_BUY/BUY/WATCH_BUY/HOLD/REDUCE/STRONG_SELL/WAIT）
- 置信度：（0-100%）
- 操作建议：（具体的入场/持仓/离场建议）
- 入场条件：（什么条件满足后执行）
- 止损条件：（什么条件触发止损）
- 目标区间：（保守/中间/激进三个目标位）

### 5. 风险提示
（最需要警惕的风险因素）"""

    def judge_reaccumulation_vs_redistribution(self, context: dict) -> dict:
        """再吸筹vs再派发的AI判定
        
        这是整个系统中最需要LLM的场景：
        上涨/下跌途中出现横盘TR，需判断是中继整理还是趋势反转。
        纯规则引擎在此场景准确率有限，LLM可综合多维模糊证据。
        """
        prompt = f"""在上涨趋势中途出现了一个震荡区间（TR），请判断它是"再吸筹"（牛市中继，后续恢复上涨）还是"再派发"（趋势反转，后续转为下跌）。

## TR区间信息
- 上沿：{context['tr_upper']:.3f}
- 下沿：{context['tr_lower']:.3f}
- 持续天数：{context['tr_days']}天
- 区间内出现的信号：{json.dumps(context['tr_signals'], ensure_ascii=False)}

## 判定线索
1. 回调时的量能特征：{context['pullback_volume_pattern']}
2. 反弹时的量能特征：{context['rally_volume_pattern']}
3. 是否出现了SOS/SOW：{context['sos_or_sow']}
4. 是否出现了Spring/UT：{context['spring_or_ut']}
5. 前一段上涨的幅度和速度：{context['prior_trend_info']}

请给出你的判定（再吸筹/再派发），置信度（0-100%），以及详细的推理过程。"""
        
        response = self.client.messages.create(
            model=self.model, max_tokens=2000,
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )
        return self._parse_judgment(response.content[0].text)

    def generate_daily_briefing(self, watchlist_results: list[dict]) -> str:
        """生成每日盘前简报
        
        输入所有自选股的量化分析结果，
        LLM综合生成一份结构化的每日简报，
        包括：今日重点关注标的、各标的的阶段变化、新触发的信号、建议操作。
        """
        prompt = f"""请基于以下{len(watchlist_results)}只自选股的分析结果，生成今日盘前简报：

{json.dumps(watchlist_results, ensure_ascii=False, indent=2)}

简报格式：
1. **今日市场环境概述**（大盘阶段+整体氛围）
2. **重点关注标的**（信号链完成度最高的前3只）
3. **新触发信号汇总**（昨日新出现的所有信号）
4. **持仓股跟踪**（已持仓标的的阶段变化和建议）
5. **风险警报**（出现不利信号的标的）"""
        
        response = self.client.messages.create(
            model=self.model, max_tokens=3000,
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
```

### 5.3 AI融合的六大场景

| 场景 | 触发时机 | LLM输入 | LLM输出 | 为什么需要AI |
|------|---------|---------|---------|-------------|
| 个股综合研判 | 信号链完成度≥50%或用户手动触发 | 阶段+信号+量价统计+多时间框架 | 建议类型+置信度+推理链 | 综合多维度模糊证据做定性判断 |
| 再吸筹vs再派发判定 | TR形成且持续≥15日 | TR内部量价特征+前序趋势信息 | 判定结果+置信度+推理 | 纯规则引擎准确率不足，需模糊推理 |
| 异常行情解读 | 单日涨跌幅>7%或成交量>5倍均量 | 异常日的量价数据+近期背景 | 解读该异常行为的含义 | 突发事件需要语境理解 |
| 每日盘前简报 | 每日8:30自动触发 | 全部自选股的扫描结果 | 结构化中文简报 | 人类消费信息需要自然语言 |
| 交易计划复核 | 用户确认交易计划前 | 计划内容+当前市场数据 | 风险评估+改进建议 | 提供第二意见，避免冲动交易 |
| 复盘分析 | 盘后用户发起 | 当日所有操作+市场表现 | 操作评价+改进建议 | 需要反思性推理能力 |

### 5.4 Prompt模板管理

```python
# file: wyckoffpro/ai/prompts.py

PROMPTS = {
    'stock_analysis': """...""",       # 见5.2节
    'reaccum_vs_redist': """...""",     # 见5.2节  
    'daily_briefing': """...""",        # 见5.2节
    'anomaly_interpretation': """
一只处于{phase}阶段的股票今天出现了异常行情：
- 涨跌幅：{pct_change}%
- 成交量：{volume}手（是近20日均量的{vol_ratio}倍）
- K线形态：{candle_description}

请基于威科夫理论解读这个异常行为的含义：
1. 这是供应事件还是需求事件？
2. 对当前阶段判定有什么影响？
3. 后续应该关注什么行为来确认？
""",
    'plan_review': """
用户准备执行以下交易计划，请进行风险复核：
- 股票：{code} {name}
- 方向：{direction}
- 入场模式：{entry_mode}
- 入场价：{entry_price}
- 止损价：{stop_loss}
- 目标价：{target_1} / {target_2}
- 风险回报比：{risk_reward}

当前市场数据：
{market_context}

请评估：
1. 这个计划的逻辑是否自洽？
2. 止损位是否合理（是否在关键支撑/阻力的正确一侧）？
3. 最大的风险是什么？
4. 你的改进建议？
""",
}
```

---

## 第六章 M10 - 点数图引擎

### 6.1 P&F图计算

```python
# file: wyckoffpro/engine/pnf.py

class PointAndFigure:
    """点数图计算引擎"""
    
    def __init__(self, box_size: float = None, reversal: int = 3):
        self.box_size = box_size   # None=自适应
        self.reversal = reversal
        self.columns = []          # 每列: {'direction': 'X'/'O', 'start': float, 'end': float}
    
    def build(self, df: pd.DataFrame) -> list[dict]:
        """从日K线数据构建P&F图"""
        if self.box_size is None:
            self.box_size = self._auto_box_size(df)
        
        prices = df['close'].values
        self.columns = []
        current_dir = None  # 'X'=上涨, 'O'=下跌
        current_col = None
        
        for price in prices:
            box_price = self._round_to_box(price)
            
            if current_col is None:
                current_col = {'direction': 'X', 'start': box_price, 'end': box_price, 'count': 1}
                current_dir = 'X'
                continue
            
            if current_dir == 'X':
                if box_price > current_col['end']:
                    current_col['end'] = box_price
                    current_col['count'] += 1
                elif (current_col['end'] - box_price) >= self.box_size * self.reversal:
                    self.columns.append(current_col)
                    current_col = {'direction': 'O', 'start': current_col['end'] - self.box_size,
                                   'end': box_price, 'count': 1}
                    current_dir = 'O'
            else:  # O column
                if box_price < current_col['end']:
                    current_col['end'] = box_price
                    current_col['count'] += 1
                elif (box_price - current_col['end']) >= self.box_size * self.reversal:
                    self.columns.append(current_col)
                    current_col = {'direction': 'X', 'start': current_col['end'] + self.box_size,
                                   'end': box_price, 'count': 1}
                    current_dir = 'X'
        
        if current_col:
            self.columns.append(current_col)
        return self.columns
    
    def horizontal_count(self, lps_price: float, tr_start_col: int, tr_end_col: int) -> dict:
        """水平计数法计算目标价
        
        从LPS所在列向左数TR范围内的列数
        目标价 = LPS价格 + (列数 × 格值 × 转向数)
        
        Returns:
            {'conservative': float, 'moderate': float, 'aggressive': float}
        """
        col_count = tr_end_col - tr_start_col + 1
        projection = col_count * self.box_size * self.reversal
        
        tr_low = min(c['end'] for c in self.columns[tr_start_col:tr_end_col+1] if c['direction'] == 'O')
        
        return {
            'conservative': tr_low + projection * 0.6,
            'moderate': lps_price + projection * 0.8,
            'aggressive': lps_price + projection,
        }
    
    def _auto_box_size(self, df):
        avg_price = df['close'].mean()
        return round(avg_price * 0.01, 2)  # 1%为一格
    
    def _round_to_box(self, price):
        return round(price / self.box_size) * self.box_size
```

---

## 第七章 A股适配层

```python
# file: wyckoffpro/adapters/a_share.py

class AShareAdapter:
    """A股特殊机制适配器"""
    
    @staticmethod
    def is_limit_up(row: pd.Series, is_st: bool = False) -> bool:
        """判断是否涨停"""
        limit = 5.0 if is_st else 10.0  # 创业板/科创板20%需另判
        return row['pct_change'] >= limit - 0.1
    
    @staticmethod
    def is_limit_down(row: pd.Series, is_st: bool = False) -> bool:
        limit = 5.0 if is_st else 10.0
        return row['pct_change'] <= -(limit - 0.1)
    
    @staticmethod
    def detect_limit_climax(df: pd.DataFrame, direction: str) -> Optional[dict]:
        """检测涨停/跌停板形式的高潮行为
        
        连续涨停后首次开板放量 → BC信号
        连续跌停后首次开板放量 → SC信号
        """
        recent = df.tail(10)
        
        if direction == 'up':
            # 查找连续涨停后首次非涨停日
            limit_streak = 0
            for i in range(len(recent)-2, -1, -1):
                if AShareAdapter.is_limit_up(recent.iloc[i]):
                    limit_streak += 1
                else:
                    break
            
            if limit_streak >= 2:  # 至少2个连续涨停
                today = recent.iloc[-1]
                if not AShareAdapter.is_limit_up(today):
                    # 首次开板，且成交量大幅放大
                    if today['volume'] > recent['volume'].mean() * 2:
                        return {
                            'type': 'BC',
                            'streak': limit_streak,
                            'open_board_volume': today['volume'],
                            'date': str(today.name)
                        }
        
        # direction == 'down' 逻辑对称
        return None
    
    @staticmethod
    def adjust_entry_for_t1(plan: dict) -> dict:
        """T+1制度下的入场价调整
        
        信号日收盘确认后，入场价改为次日开盘
        止损需包含隔夜风险溢价（+0.5%）
        """
        plan['entry_note'] = '信号日收盘确认，次日开盘入场'
        plan['t1_risk_premium'] = 0.005  # 0.5%隔夜风险
        
        if plan['direction'] == 'LONG':
            plan['stop_loss'] = plan['stop_loss'] * (1 - plan['t1_risk_premium'])
        
        return plan
```

---

## 第八章 主流程编排

```python
# file: wyckoffpro/main.py

class WyckoffPro:
    """系统主入口"""
    
    def __init__(self, config_path: str = 'config.yaml'):
        self.config = load_config(config_path)
        self.data = TushareProvider(self.config['tushare_token'])
        self.phase_engine = PhaseEngine(self.config)
        self.signal_detectors = self._init_detectors()
        self.chain_tracker = {}  # code -> SignalChainTracker
        self.pnf = PointAndFigure()
        self.llm = WyckoffLLM(self.config['anthropic_api_key'])
        self.db = Database(self.config['db_path'])
    
    def analyze_stock(self, code: str, use_ai: bool = True) -> dict:
        """对单只股票执行完整的威科夫分析
        
        这是系统的核心方法，编排所有模块的执行顺序。
        """
        # 1. 获取数据
        df_daily = self.data.get_daily_kline(code, start='-2y')
        df_weekly = resample_to_weekly(df_daily)
        df_60min = self.data.get_minute_kline(code, '60min', start='-60d')
        
        # 2. 多时间框架阶段识别
        phase_weekly = self.phase_engine.identify_phase(code, df_weekly)
        phase_daily = self.phase_engine.identify_phase(code, df_daily)
        phase_60min = self.phase_engine.identify_phase(code, df_60min) if df_60min is not None else None
        
        # 3. 信号检测（日线）
        threshold = AdaptiveThreshold(df_daily)
        signals_today = []
        for detector in self.signal_detectors:
            sig = detector.detect(df_daily, phase_daily, threshold)
            if sig:
                # 贝叶斯评分：查询历史同类信号的统计数据
                sig = self._enrich_bayes_stats(sig, code)
                signals_today.append(sig)
        
        # 4. 信号链更新
        chain = self._get_or_create_chain(code, phase_daily)
        for sig in signals_today:
            chain.feed_signal(sig)
        
        # 5. P&F目标价（如果在TR中）
        pnf_targets = None
        if phase_daily.tr_upper and phase_daily.tr_lower:
            pnf_data = self.pnf.build(df_daily)
            pnf_targets = self.pnf.horizontal_count(
                lps_price=phase_daily.tr_lower,
                tr_start_col=0, tr_end_col=len(pnf_data)-1
            )
        
        # 6. 构建分析上下文
        context = {
            'stock_info': self.db.get_stock_info(code),
            'current_phase': phase_daily.__dict__,
            'recent_signals': [s.__dict__ for s in self._get_recent_signals(code, 10)],
            'signal_chain': {
                'type': chain.chain_type,
                'completion': chain.completion,
                'events': [e['event'] for e in chain.triggered_events]
            },
            'kline_summary': self._calc_kline_summary(df_daily),
            'market_phase': self.phase_engine.identify_phase('000001.SH', 
                            self.data.get_index_daily('000001.SH', '-2y')).__dict__,
            'relative_strength': self._calc_relative_strength(code, df_daily),
            'support_resistance': self._get_sr_levels(code),
            'multi_timeframe': {
                'weekly': phase_weekly.code,
                'daily': phase_daily.code,
                '60min': phase_60min.code if phase_60min else 'N/A'
            },
            'pnf_targets': pnf_targets,
        }
        
        # 7. AI研判（可选）
        ai_result = None
        if use_ai and self.config.get('enable_ai', True):
            ai_result = self.llm.analyze_stock(context)
        
        # 8. 汇总输出
        return {
            'context': context,
            'signals_today': [s.__dict__ for s in signals_today],
            'chain_completion': chain.completion,
            'pnf_targets': pnf_targets,
            'ai_advice': ai_result,
        }
    
    def scan_watchlist(self, use_ai: bool = False) -> list[dict]:
        """批量扫描自选股"""
        watchlist = self.db.get_watchlist()
        results = []
        for code in watchlist:
            try:
                result = self.analyze_stock(code, use_ai=False)  # 批量扫描不用AI（节省API调用）
                results.append(result)
            except Exception as e:
                print(f"Error scanning {code}: {e}")
        
        # 按信号链完成度排序
        results.sort(key=lambda x: x['chain_completion'], reverse=True)
        
        # 对前5名使用AI生成简要建议
        if use_ai:
            for r in results[:5]:
                r['ai_advice'] = self.llm.analyze_stock(r['context'])
        
        return results
    
    def generate_morning_briefing(self) -> str:
        """生成每日盘前简报"""
        results = self.scan_watchlist(use_ai=False)
        return self.llm.generate_daily_briefing(results)
```

---

## 第九章 配置文件

```yaml
# file: config.yaml

# 数据源
tushare_token: "your_tushare_token_here"

# AI引擎
anthropic_api_key: "your_anthropic_key_here"
enable_ai: true

# 数据库
db_path: "./data/wyckoffpro.db"

# 自适应阈值基础参数（这些是自适应计算的基线，大多数情况下不需要修改）
thresholds:
  climax_vol_multiple_base: 2.5
  climax_range_multiple_base: 2.0
  spring_max_penetration_base: 0.03
  st_vol_ratio: 0.60
  joc_vol_multiple: 1.8
  tr_min_days_base: 20
  tr_max_amplitude_base: 0.20
  sot_threshold: 0.50
  evr_vol_ratio: 1.5
  evr_pct_ratio: 0.5
  dead_corner_min_bars: 8
  dead_corner_range_compression: 0.4
  rr_minimum: 3.0  # 威科夫最低盈亏比要求

# 多时间框架
timeframes:
  direction: "weekly"     # 定方向
  timing: "daily"         # 定时机
  entry: "60min"          # 精入场

# 回测
backtest:
  start_date: "2018-01-01"
  end_date: "2025-12-31"
  initial_capital: 1000000
  commission_rate: 0.001
  slippage_rate: 0.001

# 预警
alerts:
  sound_enabled: true
  popup_enabled: true
```

---

## 第十章 开发阶段规划

### Phase 1（6周）：核心闭环
- W1-2：M1数据层 + SQLite + 自适应阈值计算
- W3-4：M2阶段引擎（概率FSM + 规则引擎） + M3信号检测（13种）+ 信号链追踪
- W5-6：M4图表UI（Streamlit + lightweight-charts） + M11 AI研判引擎对接

### Phase 2（4周）：交易闭环
- W7-8：M5交易计划 + M6风控 + M10点数图 + A股适配层
- W9-10：多时间框架联动 + 每日盘前简报 + 批量扫描

### Phase 3（4周）：回测与优化
- W11-12：M7回测引擎 + 贝叶斯信号评分统计
- W13-14：参数优化 + AI Prompt调优 + 全系统集成测试

---

## 第十一章 目录结构

```
wyckoffpro/
├── config.yaml                    # 全局配置
├── schema.sql                     # 数据库建表语句
├── main.py                        # 系统主入口
├── data/
│   ├── provider.py                # 数据源抽象接口
│   ├── tushare_provider.py        # Tushare实现
│   └── database.py                # SQLite操作封装
├── engine/
│   ├── adaptive_threshold.py      # 自适应阈值计算器
│   ├── phase_fsm.py               # 概率状态机
│   ├── phase_engine.py            # 阶段识别主引擎
│   ├── signal_chain.py            # 信号链追踪器
│   ├── pnf.py                     # 点数图引擎
│   └── signals/
│       ├── base.py                # 信号检测基类
│       ├── selling_climax.py      # SC检测
│       ├── buying_climax.py       # BC检测
│       ├── spring.py              # Spring检测
│       ├── shakeout.py            # 终极震仓检测
│       ├── joc.py                 # JOC检测
│       ├── sos.py                 # SOS检测
│       ├── sow.py                 # SOW检测
│       ├── upthrust.py            # UT检测
│       ├── sot.py                 # SOT检测
│       ├── vdb_vsb.py             # VDB/VSB检测
│       ├── ice_break.py           # 破冰检测
│       ├── effort_vs_result.py    # EvR检测
│       └── dead_corner.py         # 死角检测
├── adapters/
│   └── a_share.py                 # A股特殊适配
├── ai/
│   ├── llm_engine.py              # LLM研判引擎
│   └── prompts.py                 # Prompt模板管理
├── trading/
│   ├── plan_generator.py          # 交易计划生成器
│   ├── risk_manager.py            # 风险管理
│   └── position_calculator.py     # 仓位计算器
├── backtest/
│   ├── engine.py                  # 回测引擎
│   └── reporter.py                # 回测报告生成
└── ui/
    ├── app.py                     # Streamlit主页面
    ├── components/
    │   ├── chart.py               # K线图表组件
    │   ├── signal_panel.py        # 信号面板
    │   ├── advice_card.py         # 建议卡片
    │   └── scanner.py             # 扫描结果表格
    └── pages/
        ├── dashboard.py           # 主看盘页
        ├── scanner_page.py        # 全市场扫描页
        ├── plan_page.py           # 交易计划页
        └── backtest_page.py       # 回测页
```

---

*本文档可直接用于指导AI辅助开发。每个代码块均为可执行的Python代码框架，开发者（或AI）应在此基础上补全具体实现细节。*
