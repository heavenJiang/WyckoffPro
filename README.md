# WyckoffPro V3.1 📈

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Streamlit App](https://img.shields.io/badge/Streamlit-UI-FF4B4B.svg)](https://streamlit.io/)

**WyckoffPro V3.1** 是一套基于孟洪涛《威科夫操盘法》核心理论，并结合大语言模型 (DeepSeek) 增强验证的本地化量价分析辅助交易系统。

本系统旨在消除传统基于形态学的主观交易盲区，通过强规则驱动的**状态机(FSM)**追踪价格周期，运用创新的**AI反向证伪(Falsification)**机制过滤假信号，为您提供高胜率、严格风控的量化投资参考。

---

## 🎯 核心功能 (Core Features)

* **🚦 11维多态智能流转系统 (Phase FSM)**
  * 利用状态机追踪从吸筹(Accumulation)、上涨(Markup)、派发(Distribution)到下跌(Markdown)的11个细分威科夫阶段。
  * 内置核心**紧急反转系统(Emergency Reversal)**：当反面证据追踪(Counter-Evidence Tracker)积分 ≥ 71 时，绕过常规信号强行终止当前趋势预判。

* **🤖 逆向思维大模型证伪引擎 (Falsification Engine)**
  * 突破常规的LLM正向判定，要求大模型专门扮演"找茬/唱反调"角色。
  * **三层证伪**: 阶段前提检验 (Prompt A) -> 信号审计 (Prompt B) -> 叙事一致性打分 (Prompt C)。
  * **智能预算与惩罚机制**: 具备调用冷却期(Cooldown)功能，节省API成本并阻止过度交易。

* **🧩 13大威科夫标准事件全覆盖**
  * 量化侦测 SC(卖出高潮)、AR(自动反弹)、ST(二次测试)、Spring(弹簧效应)、JOC(跳出冰点)、UTAD(末期试探) 等关键量价事件，运用自适应120日历史动态分位来计算量价异常阙值。

* **📊 可视化与自动化交易计划生成 (UI & Trade)**
  * 基于 Streamlit 构建的轻量级本地控制台。
  * 配备丰富的交互式 K 线图与点数图 (P&F Chart)，自动化绘制 Creek/Ice 系统支撑与阻力位。
  * 单笔防爆仓原则：自动计算止盈止损与仓位占比，将单笔交易额严格限制在 < 2% 总资产内。

---

## ⚙️ 系统架构 (Architecture)

1. **`data/` (数据层)**：整合 Tushare (Primary) 与 AkShare (Fallback)，支持 SQLite3 本地高速缓存和日线级别指标修正。
2. **`engine/` (核心引擎层)**：13型信号判定，九大检验，阶段转移机，反面证据积分表。
3. **`ai/` (智能层)**：适配 OpenAI SDK 协议接入 DeepSeek，处理复杂的行情叙事一致性判断。
4. **`trade/` (交易层)**：持仓台账追踪、投资顾问 L4 防护门控。
5. **`ui/` (前端层)**：基于 Streamlit 框架，提供 Dashboard、多股 Scanner 等直观管理体验。

---

## 🚀 安装部署 (Installation)

### 1. 环境要求 (Prerequisites)
* **Python**: `🚀 >= 3.11` (推荐使用虚拟环境如 `conda` 或 `venv`)
* **OS**: 兼容 MacOS / Linux / Windows

### 2. 获取代码与依赖安装
```bash
# 激活你的虚拟环境 (例如 conda activate wyckoff)
pip install -r requirements.txt
```

### 3. 配置系统 (Configuration)
编辑项目的全局配置文件：`config/default.yaml`

你需要准备以下必要组件:
1. [Tushare Pro 账号 Token](https://tushare.pro/register) (用于行情数据源获取)
2. [DeepSeek API Key](https://platform.deepseek.com/) (用于支持AI逆向证伪)

```yaml
# config/default.yaml 修改示例
data:
  tushare_token: "YOUR_TUSHARE_TOKEN_HERE" 

ai:
  enabled: true
  api_key: "YOUR_DEEPSEEK_API_KEY_HERE"
  api_base_url: "https://api.deepseek.com"
  model: "deepseek-chat"
```

---

## 💻 使用说明 (Usage)

启动 Streamlit 交互式界面：

```bash
streamlit run ui/app.py
```

终端执行完毕后，通常您的默认浏览器会自动打开 `http://localhost:8501`。
你可以通过主界面的 **Settings (设置)** 录入你要监控并分析的标的代码 (例：`000001.SZ`, `600519.SH`)，然后切换到 **Scanner (扫描)** 一键执行分析管线。

---

## 🧪 单元测试 (Testing)

项目内嵌针对交易引擎信号捕捉和风控机制的测试文件：
```bash
pytest tests/
```

---

## 📂 目录结构 (Directory Structure)

```text
WyckoffPro/
├── ai/                      # AI 证伪机制和 LLM 客户端
│   └── prompts/             # 逆向思维体系提示词模板
├── backtest/                # 向量化策略历史回测引擎
├── config/                  # 系统 YAML 配置及 Watchlist
├── data/                    # SQLite 存储、采集器和清理器
├── doc/                     # 威科夫系统设计理论与开发指导
├── engine/                  # 威科夫量价 FSM 与评分核心算法
├── trade/                   # 风险控制与自动化交易方案
├── tests/                   # 单元测试模块
├── ui/                      # Streamlit 前端视图层
├── main.py                  # 触发全局 Daily 分析计算的入口
├── requirements.txt         # Python 依赖清单
└── README.md                # 文档
```

---

## ⚠️ 免责声明 (Disclaimer)

**WyckoffPro** 及其相关的衍生 AI 分析结论完全是一个供量化探索与理论研究使用的个人开源框架项目！ 
本软件以及包含的所有自动交易逻辑**不构成任何投资或财务建议**！ 股票市场时刻都在不可预测的变化中，使用本工具产生的一切交易盈亏或爆仓风险均由使用者**自行负责**。

---

## 🤝 贡献说明 (Contributing)

如果您对威科夫理论以及本项目中的改良思路感兴趣，欢迎提交 Pull Request (PR) 优化。
1. Fork 此分支
2. 创建自己独特功能的开发分支 (`git checkout -b feature/AmazingFeature`)
3. Commit 提交改动 (`git commit -m 'Add some AmazingFeature'`)
4. Push 到仓库分支 (`git push origin feature/AmazingFeature`)
5. 开启一次 Pull Request

---

## 📄 许可证 (License)

本项目采用 [MIT License](LICENSE) 许可协议。
