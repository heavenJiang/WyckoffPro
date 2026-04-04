-- WyckoffPro V3.1 扩展 Schema（Tushare Hub 全量数据）
-- 由 data/tushare_hub.py 负责写入

-- ═══════════════════════════════════════
-- 基础数据
-- ═══════════════════════════════════════

-- 全量A股列表
CREATE TABLE IF NOT EXISTS stock_basic (
    ts_code     TEXT PRIMARY KEY,
    symbol      TEXT,
    name        TEXT,
    area        TEXT,
    industry    TEXT,
    market      TEXT,       -- 主板/创业板/科创板
    list_date   TEXT,
    delist_date TEXT,
    is_hs       TEXT,       -- 沪深港通标识 N/H/S
    updated_at  TEXT
);

-- ETF列表
CREATE TABLE IF NOT EXISTS etf_basic (
    ts_code    TEXT PRIMARY KEY,
    name       TEXT,
    fund_type  TEXT,
    found_date TEXT,
    market     TEXT,
    updated_at TEXT
);

-- 期权列表
CREATE TABLE IF NOT EXISTS option_basic (
    ts_code       TEXT PRIMARY KEY,
    name          TEXT,
    underlying_code TEXT,
    call_put      TEXT,    -- C/P
    exercise_type TEXT,
    list_date     TEXT,
    delist_date   TEXT,
    updated_at    TEXT
);

-- ST股票列表（当前有效）
CREATE TABLE IF NOT EXISTS st_stocks (
    ts_code   TEXT PRIMARY KEY,
    name      TEXT,
    start_date TEXT,
    end_date  TEXT,
    updated_at TEXT
);

-- 沪深港通成分股
CREATE TABLE IF NOT EXISTS hs_const (
    ts_code  TEXT NOT NULL,
    hs_type  TEXT NOT NULL,   -- SH/SZ
    in_date  TEXT,
    out_date TEXT,
    is_new   TEXT,
    updated_at TEXT,
    PRIMARY KEY (ts_code, hs_type)
);

-- ═══════════════════════════════════════
-- 财务数据（按股票+报告期存储）
-- ═══════════════════════════════════════

-- 利润表（关键字段）
CREATE TABLE IF NOT EXISTS financial_income (
    ts_code    TEXT NOT NULL,
    ann_date   TEXT,
    end_date   TEXT NOT NULL,
    report_type TEXT,
    revenue    REAL,       -- 营业收入
    n_income   REAL,       -- 净利润
    operate_profit REAL,   -- 营业利润
    ebit       REAL,
    ebitda     REAL,
    updated_at TEXT,
    PRIMARY KEY (ts_code, end_date, report_type)
);

-- 资产负债表（关键字段）
CREATE TABLE IF NOT EXISTS financial_balance (
    ts_code      TEXT NOT NULL,
    ann_date     TEXT,
    end_date     TEXT NOT NULL,
    report_type  TEXT,
    total_assets REAL,
    total_liab   REAL,
    total_hldr_eqy_inc_min_int REAL,  -- 股东权益合计
    money_cap    REAL,       -- 货币资金
    updated_at   TEXT,
    PRIMARY KEY (ts_code, end_date, report_type)
);

-- 现金流量表（关键字段）
CREATE TABLE IF NOT EXISTS financial_cashflow (
    ts_code      TEXT NOT NULL,
    ann_date     TEXT,
    end_date     TEXT NOT NULL,
    report_type  TEXT,
    n_cashflow_act REAL,    -- 经营活动现金流量净额
    n_cashflow_inv_act REAL, -- 投资活动现金流量净额
    n_cashflow_fnc_act REAL, -- 筹资活动现金流量净额
    free_cashflow REAL,
    updated_at   TEXT,
    PRIMARY KEY (ts_code, end_date, report_type)
);

-- 财务指标（核心因子）
CREATE TABLE IF NOT EXISTS financial_indicator (
    ts_code      TEXT NOT NULL,
    ann_date     TEXT,
    end_date     TEXT NOT NULL,
    eps          REAL,       -- 基本每股收益
    bps          REAL,       -- 每股净资产
    roe          REAL,       -- 净资产收益率
    roa          REAL,       -- 总资产收益率
    grossprofit_margin REAL, -- 销售毛利率
    netprofit_margin   REAL, -- 销售净利率
    debt_to_assets     REAL, -- 资产负债率
    current_ratio      REAL, -- 流动比率
    quick_ratio        REAL, -- 速动比率
    pe              REAL,
    pb              REAL,
    updated_at   TEXT,
    PRIMARY KEY (ts_code, end_date)
);

-- 业绩预告
CREATE TABLE IF NOT EXISTS forecast (
    ts_code     TEXT NOT NULL,
    ann_date    TEXT,
    end_date    TEXT NOT NULL,
    type        TEXT,       -- 预增/预减/扭亏/首亏等
    p_change_min REAL,
    p_change_max REAL,
    net_profit_min REAL,
    net_profit_max REAL,
    last_parent_net REAL,
    summary     TEXT,
    updated_at  TEXT,
    PRIMARY KEY (ts_code, ann_date, end_date)
);

-- 分红送股
CREATE TABLE IF NOT EXISTS dividend (
    ts_code     TEXT NOT NULL,
    end_date    TEXT NOT NULL,
    ann_date    TEXT,
    div_proc    TEXT,       -- 实施进度
    stk_div     REAL,       -- 每股送转股份
    cash_div    REAL,       -- 每股现金分红（税前）
    cash_div_tax REAL,      -- 每股现金分红（税后）
    record_date TEXT,
    ex_date     TEXT,
    pay_date    TEXT,
    updated_at  TEXT,
    PRIMARY KEY (ts_code, end_date, ann_date)
);

-- ═══════════════════════════════════════
-- 宏观经济
-- ═══════════════════════════════════════

CREATE TABLE IF NOT EXISTS macro_gdp (
    quarter    TEXT PRIMARY KEY,  -- 如 2023Q4
    gdp        REAL,
    gdp_yoy    REAL,   -- 同比增速%
    pi         REAL,   -- 第一产业
    si         REAL,   -- 第二产业
    ti         REAL,   -- 第三产业
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS macro_cpi (
    month      TEXT PRIMARY KEY,  -- 如 202312
    nt_val     REAL,  -- CPI全国当月值
    nt_yoy     REAL,  -- CPI全国同比
    nt_mom     REAL,  -- CPI全国环比
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS macro_money (
    month      TEXT PRIMARY KEY,  -- 如 202312
    m0         REAL,
    m0_yoy     REAL,
    m1         REAL,
    m1_yoy     REAL,
    m2         REAL,
    m2_yoy     REAL,
    updated_at TEXT
);

-- ═══════════════════════════════════════
-- 参考数据
-- ═══════════════════════════════════════

-- 股权质押统计
CREATE TABLE IF NOT EXISTS pledge_stat (
    ts_code         TEXT NOT NULL,
    end_date        TEXT NOT NULL,
    pledge_count    INTEGER,  -- 质押次数
    unrest_pledged  REAL,     -- 无限售股质押数量
    rest_pledged    REAL,     -- 限售股质押数量
    total_shares    REAL,     -- 总股本
    pledge_ratio    REAL,     -- 质押比例%
    updated_at      TEXT,
    PRIMARY KEY (ts_code, end_date)
);

-- 限售股解禁
CREATE TABLE IF NOT EXISTS share_float (
    ts_code      TEXT NOT NULL,
    ann_date     TEXT,
    float_date   TEXT NOT NULL,  -- 解禁日期
    float_share  REAL,           -- 流通股份
    float_ratio  REAL,           -- 解禁比例%
    holder_name  TEXT,
    share_type   TEXT,
    updated_at   TEXT,
    PRIMARY KEY (ts_code, float_date, holder_name)
);

-- 股票回购
CREATE TABLE IF NOT EXISTS repurchase (
    ts_code     TEXT NOT NULL,
    ann_date    TEXT,
    end_date    TEXT,
    proc        TEXT,    -- 进度
    exp_date    TEXT,    -- 截止日期
    vol         REAL,    -- 回购数量
    amount      REAL,    -- 回购金额
    high_limit  REAL,    -- 回购最高价格
    low_limit   REAL,    -- 回购最低价格
    updated_at  TEXT,
    PRIMARY KEY (ts_code, ann_date)
);

-- 股东增减持
CREATE TABLE IF NOT EXISTS holder_trade (
    ts_code      TEXT NOT NULL,
    ann_date     TEXT NOT NULL,
    holder_name  TEXT,
    holder_type  TEXT,  -- G高管/P大股东
    in_de        TEXT,  -- IN增持/DE减持
    change_vol   REAL,
    change_ratio REAL,
    after_vol    REAL,
    after_ratio  REAL,
    avg_price    REAL,
    updated_at   TEXT,
    PRIMARY KEY (ts_code, ann_date, holder_name)
);

-- 龙虎榜（每日）
CREATE TABLE IF NOT EXISTS top_list (
    ts_code     TEXT NOT NULL,
    trade_date  TEXT NOT NULL,
    name        TEXT,
    close       REAL,
    pct_change  REAL,
    turnover_rate REAL,
    amount      REAL,
    l_sell      REAL,   -- 龙虎榜卖出额
    l_buy       REAL,   -- 龙虎榜买入额
    l_amount    REAL,   -- 龙虎榜成交额
    net_amount  REAL,   -- 龙虎榜净买入额
    reason      TEXT,   -- 上榜原因
    updated_at  TEXT,
    PRIMARY KEY (ts_code, trade_date)
);

-- 融资融券汇总
CREATE TABLE IF NOT EXISTS margin (
    ts_code      TEXT NOT NULL,
    trade_date   TEXT NOT NULL,
    rzye         REAL,   -- 融资余额
    rqye         REAL,   -- 融券余额
    rzrqye       REAL,   -- 融资融券余额
    rzmre        REAL,   -- 融资买入额
    rqmcl        REAL,   -- 融券卖出量
    updated_at   TEXT,
    PRIMARY KEY (ts_code, trade_date)
);

-- ═══════════════════════════════════════
-- 特色数据
-- ═══════════════════════════════════════

-- 概念板块列表
CREATE TABLE IF NOT EXISTS concept (
    concept_code TEXT PRIMARY KEY,
    concept_name TEXT,
    src          TEXT,   -- 来源
    updated_at   TEXT
);

-- 概念板块成分
CREATE TABLE IF NOT EXISTS concept_detail (
    concept_code TEXT NOT NULL,
    ts_code      TEXT NOT NULL,
    name         TEXT,
    updated_at   TEXT,
    PRIMARY KEY (concept_code, ts_code)
);

-- 个股资金流向（每日）
CREATE TABLE IF NOT EXISTS moneyflow (
    ts_code       TEXT NOT NULL,
    trade_date    TEXT NOT NULL,
    buy_sm_vol    INTEGER,   -- 小单买入量
    sell_sm_vol   INTEGER,   -- 小单卖出量
    buy_md_vol    INTEGER,   -- 中单买入量
    sell_md_vol   INTEGER,   -- 中单卖出量
    buy_lg_vol    INTEGER,   -- 大单买入量
    sell_lg_vol   INTEGER,   -- 大单卖出量
    buy_elg_vol   INTEGER,   -- 超大单买入量
    sell_elg_vol  INTEGER,   -- 超大单卖出量
    net_mf_vol    INTEGER,   -- 净流入量
    net_mf_amount REAL,      -- 净流入额（万元）
    updated_at    TEXT,
    PRIMARY KEY (ts_code, trade_date)
);

-- 券商金股（月度）
CREATE TABLE IF NOT EXISTS broker_recommend (
    month       TEXT NOT NULL,
    broker      TEXT NOT NULL,
    ts_code     TEXT NOT NULL,
    name        TEXT,
    reason      TEXT,
    updated_at  TEXT,
    PRIMARY KEY (month, broker, ts_code)
);

-- 筹码分布（每日，仅存最近两期）
CREATE TABLE IF NOT EXISTS cyq_perf (
    ts_code      TEXT NOT NULL,
    trade_date   TEXT NOT NULL,
    his_low      REAL,    -- 历史最低价
    his_high     REAL,    -- 历史最高价
    cost_5pct    REAL,    -- 5%集中度对应成本
    cost_15pct   REAL,
    cost_50pct   REAL,    -- 中位成本
    cost_85pct   REAL,
    cost_95pct   REAL,
    winner_rate  REAL,    -- 获利盘比例%
    updated_at   TEXT,
    PRIMARY KEY (ts_code, trade_date)
);

-- 量化因子（每日）
CREATE TABLE IF NOT EXISTS stk_factor (
    ts_code     TEXT NOT NULL,
    trade_date  TEXT NOT NULL,
    close       REAL,
    open        REAL,
    high        REAL,
    low         REAL,
    pre_close   REAL,
    change      REAL,
    pct_chg     REAL,
    vol         REAL,
    amount      REAL,
    adj_factor  REAL,
    turnover_rate REAL,
    turnover_rate_f REAL,  -- 自由流通换手率
    volume_ratio  REAL,    -- 量比
    pe           REAL,
    pe_ttm       REAL,
    pb           REAL,
    ps           REAL,
    ps_ttm       REAL,
    dv_ratio     REAL,     -- 股息率
    total_share  REAL,     -- 总股本（亿）
    float_share  REAL,     -- 流通股本（亿）
    free_share   REAL,     -- 自由流通股本（亿）
    total_mv     REAL,     -- 总市值（万元）
    circ_mv      REAL,     -- 流通市值（万元）
    updated_at   TEXT,
    PRIMARY KEY (ts_code, trade_date)
);

-- 盈利预测（机构一致预期）
CREATE TABLE IF NOT EXISTS report_rc (
    ts_code     TEXT NOT NULL,
    report_date TEXT NOT NULL,
    org_name    TEXT NOT NULL,
    eps         REAL,    -- 预测EPS
    pe          REAL,    -- 预测PE
    rating      TEXT,    -- 评级
    target_price REAL,   -- 目标价
    last_rating TEXT,
    updated_at  TEXT,
    PRIMARY KEY (ts_code, report_date, org_name)
);

-- 机构调研
CREATE TABLE IF NOT EXISTS stk_surv (
    ts_code      TEXT NOT NULL,
    surv_date    TEXT NOT NULL,
    org_name     TEXT NOT NULL,
    org_type     TEXT,    -- 机构类型
    rece_place   TEXT,    -- 接待地点
    rece_mode    TEXT,    -- 接待方式
    rece_org     TEXT,    -- 接待机构
    num_org      INTEGER, -- 机构数量
    updated_at   TEXT,
    PRIMARY KEY (ts_code, surv_date, org_name)
);

-- 集合竞价
CREATE TABLE IF NOT EXISTS stk_auction (
    ts_code     TEXT NOT NULL,
    trade_date  TEXT NOT NULL,
    open_price  REAL,    -- 集合竞价价格（开盘价）
    open_vol    INTEGER, -- 集合竞价成交量
    pre_close   REAL,
    updated_at  TEXT,
    PRIMARY KEY (ts_code, trade_date)
);

-- ═══════════════════════════════════════
-- 元数据：采集任务进度追踪
-- ═══════════════════════════════════════
CREATE TABLE IF NOT EXISTS hub_sync_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name   TEXT NOT NULL,    -- 任务名称
    task_type   TEXT NOT NULL,    -- DAILY/WEEKLY/MONTHLY/ONCE
    target      TEXT,             -- stock_code 或 'ALL'
    status      TEXT NOT NULL,    -- RUNNING/DONE/FAILED
    rows_saved  INTEGER DEFAULT 0,
    started_at  TEXT,
    finished_at TEXT,
    error_msg   TEXT
);
CREATE INDEX IF NOT EXISTS idx_hub_sync_log ON hub_sync_log(task_name, target, started_at);
