-- WyckoffPro V3.1 SQLite Schema

-- 日K线数据
CREATE TABLE IF NOT EXISTS kline_daily (
    stock_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    amount REAL,
    turnover_rate REAL,
    pct_change REAL,
    amplitude REAL,
    atr_20 REAL,
    PRIMARY KEY (stock_code, trade_date)
);

-- 周K线数据
CREATE TABLE IF NOT EXISTS kline_weekly (
    stock_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER, amount REAL, pct_change REAL, amplitude REAL,
    PRIMARY KEY (stock_code, trade_date)
);

-- 月K线数据
CREATE TABLE IF NOT EXISTS kline_monthly (
    stock_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER, amount REAL, pct_change REAL, amplitude REAL,
    PRIMARY KEY (stock_code, trade_date)
);

-- 小时线数据 (60min)
CREATE TABLE IF NOT EXISTS kline_hourly (
    stock_code TEXT NOT NULL,
    trade_date TEXT NOT NULL, -- 格式: YYYY-MM-DD HH:MM:SS
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER, amount REAL, pct_change REAL, amplitude REAL,
    PRIMARY KEY (stock_code, trade_date)
);

-- 威科夫阶段
CREATE TABLE IF NOT EXISTS wyckoff_phase (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    phase_code TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT,
    confidence REAL,
    tr_upper REAL,
    tr_lower REAL,
    ice_line REAL,
    creek_line REAL,
    timeframe TEXT DEFAULT 'daily',
    UNIQUE(stock_code, start_date, timeframe)
);

-- 威科夫信号
CREATE TABLE IF NOT EXISTS wyckoff_signal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    signal_date TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    likelihood REAL NOT NULL,
    strength INTEGER,
    phase_code TEXT,
    trigger_price REAL,
    trigger_volume INTEGER,
    is_confirmed INTEGER DEFAULT 0,
    confirm_date TEXT,
    ai_falsification_result TEXT,
    ai_reasoning TEXT,
    rule_detail TEXT,
    timeframe TEXT DEFAULT 'daily'
);

-- 信号链追踪
CREATE TABLE IF NOT EXISTS signal_chain (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    chain_type TEXT NOT NULL,
    start_date TEXT NOT NULL,
    events TEXT NOT NULL,
    completion_pct INTEGER,
    status TEXT DEFAULT 'ACTIVE',
    timeframe TEXT DEFAULT 'daily'
);

-- V3.1: 反面证据追踪
CREATE TABLE IF NOT EXISTS counter_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    current_score INTEGER DEFAULT 0,
    alert_level TEXT DEFAULT 'NONE',
    events TEXT,
    created_at TEXT,
    last_updated TEXT,
    is_active INTEGER DEFAULT 1
);

-- V3.1: 证伪记录
CREATE TABLE IF NOT EXISTS falsification_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    falsification_type TEXT NOT NULL,
    executed_at TEXT NOT NULL,
    result TEXT NOT NULL,
    detail TEXT,
    adjustments_applied TEXT,
    token_used INTEGER
);

-- 投资建议
CREATE TABLE IF NOT EXISTS advice (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    created_at TEXT NOT NULL,
    advice_type TEXT NOT NULL,
    confidence REAL,
    summary TEXT,
    reasoning TEXT,
    trade_plan TEXT,
    key_watch_points TEXT,
    invalidation TEXT,
    valid_until TEXT,
    quant_score REAL,
    nine_tests_passed INTEGER,
    counter_evidence_score INTEGER,
    falsification_gate TEXT,
    is_expired INTEGER DEFAULT 0
);

-- 交易计划
CREATE TABLE IF NOT EXISTS trade_plan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_mode TEXT,
    entry_price REAL,
    stop_loss REAL,
    target_1 REAL,
    target_2 REAL,
    rr_ratio REAL,
    position_pct REAL,
    status TEXT DEFAULT 'DRAFT',
    linked_advice_id INTEGER,
    created_at TEXT,
    notes TEXT
);

-- 持仓台账
CREATE TABLE IF NOT EXISTS position (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    stock_name TEXT,
    direction TEXT DEFAULT 'LONG',
    quantity INTEGER DEFAULT 0,
    cost_price REAL,
    current_price REAL,
    open_date TEXT,
    status TEXT DEFAULT 'OPEN',
    notes TEXT
);

-- 自选股
CREATE TABLE IF NOT EXISTS watchlist (
    stock_code TEXT NOT NULL,
    stock_name TEXT,
    group_name TEXT DEFAULT 'default',
    added_at TEXT,
    notes TEXT,
    PRIMARY KEY(stock_code, group_name)
);

-- 股票基本信息缓存
CREATE TABLE IF NOT EXISTS stock_info (
    stock_code TEXT PRIMARY KEY,
    stock_name TEXT,
    industry TEXT,
    market TEXT,
    list_date TEXT
);

-- 大盘指数数据（用于个股与大盘共振分析）
CREATE TABLE IF NOT EXISTS index_daily (
    index_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER, amount REAL, pct_change REAL,
    PRIMARY KEY (index_code, trade_date)
);

-- 北向资金数据
CREATE TABLE IF NOT EXISTS north_flow (
    trade_date TEXT PRIMARY KEY,
    net_amount REAL,
    buy_amount REAL,
    sell_amount REAL
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_kline_daily_code ON kline_daily(stock_code);
CREATE INDEX IF NOT EXISTS idx_wyckoff_signal_code ON wyckoff_signal(stock_code, signal_date);
CREATE UNIQUE INDEX IF NOT EXISTS idx_wyckoff_signal_unique ON wyckoff_signal(stock_code, signal_date, signal_type, timeframe);
CREATE INDEX IF NOT EXISTS idx_wyckoff_phase_code ON wyckoff_phase(stock_code);
CREATE INDEX IF NOT EXISTS idx_counter_evidence_code ON counter_evidence(stock_code, is_active);
CREATE INDEX IF NOT EXISTS idx_advice_code ON advice(stock_code, created_at);

-- 策略回测结果历史
CREATE TABLE IF NOT EXISTS backtest_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    stock_name TEXT,
    run_at TEXT NOT NULL,
    timeframe TEXT,
    entry_signals TEXT, -- JSON array
    metrics TEXT,       -- JSON object
    trades TEXT,        -- JSON array
    config_snapshot TEXT -- JSON object
);

CREATE INDEX IF NOT EXISTS idx_backtest_result_code ON backtest_result(stock_code, run_at);

-- 分析快照（每次 pipeline 运行的完整聚合记录）
CREATE TABLE IF NOT EXISTS analysis_snapshot (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code         TEXT NOT NULL,
    run_at             TEXT NOT NULL,          -- pipeline 执行时间
    timeframe          TEXT DEFAULT 'daily',
    trade_date         TEXT,                   -- 最新 K 线日期
    -- 阶段
    phase_code         TEXT,
    phase_confidence   REAL,
    -- 建议
    advice_type        TEXT,
    confidence         REAL,
    advice_id          INTEGER,                -- FK → advice.id
    -- 量化评分
    quant_total        REAL,
    sd_score           REAL,
    counter_score      REAL,
    alert_level        TEXT,
    nine_tests_passed  INTEGER,
    chain_completion   REAL,
    -- 本次检测到的信号（JSON 数组）
    signals_json       TEXT,
    -- 执行元数据
    start_time         TEXT,
    total_duration     REAL,
    steps_json         TEXT,
    -- 双轨标记：1=AI增强模式，0=纯规则模式
    ai_enabled         INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_analysis_snapshot ON analysis_snapshot(stock_code, run_at);
