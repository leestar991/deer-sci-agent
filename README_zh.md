# NextTask — GPT 虚拟临床开发团队

[English](./README.md) | 中文

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](./backend/pyproject.toml)
[![Node.js](https://img.shields.io/badge/Node.js-22%2B-339933?logo=node.js&logoColor=white)](./Makefile)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

NextTask 是一个基于 Multi-Agent 架构的 GPT 虚拟团队平台，将多个专业领域的 AI Agent 组织为一支**虚拟临床开发团队**。

与单一 Agent 不同，NextTask 的 Lead Agent 可以按需动态调度专业 Sub-Agent，让不同专业背景的"团队成员"并行协作，完成从临床方案设计、数据管理、药物注册到文件撰写的全链条任务。整个系统基于 [LangGraph](https://github.com/langchain-ai/langgraph) 和 [LangChain](https://github.com/langchain-ai/langchain) 构建，通过可扩展的 Skills 和 MCP 工具拓展能力边界。

---

## 目录

- [核心理念：GPT 虚拟临床开发团队](#核心理念gpt-虚拟临床开发团队)
- [团队成员（Sub-Agents）](#团队成员sub-agents)
- [快速开始](#快速开始)
  - [配置](#配置)
  - [运行应用](#运行应用)
    - [方式一：Docker（推荐）](#方式一docker推荐)
    - [方式二：本地开发](#方式二本地开发)
  - [进阶配置](#进阶配置)
    - [Sandbox 模式](#sandbox-模式)
    - [MCP Server](#mcp-server)
    - [IM 渠道](#im-渠道)
    - [LangSmith 链路追踪](#langsmith-链路追踪)
- [核心能力](#核心能力)
  - [Skills 与 Tools](#skills-与-tools)
  - [Sandbox 与文件系统](#sandbox-与文件系统)
  - [Context Engineering](#context-engineering)
  - [长期记忆](#长期记忆)
- [推荐模型](#推荐模型)
- [内嵌 Python Client](#内嵌-python-client)
- [文档](#文档)
- [安全使用](#安全使用)
- [参与贡献](#参与贡献)
- [许可证](#许可证)
- [致谢](#致谢)

---

## 核心理念：GPT 虚拟临床开发团队

临床药物开发涉及医学、统计、法规、CMC、生物信息、临床运营等多个高度专业化的领域，没有一个单一 Agent 能同时精通所有方向。

NextTask 的思路是：**组建一支 GPT 团队**。

每位"团队成员"都是一个深度专业化的 Sub-Agent，拥有独立的专业背景、核心能力和工作边界。Lead Agent 负责理解任务、制定计划、调度合适的成员并行工作，最终汇总出结构化的团队产出。

这让 NextTask 能够处理真实的临床开发工作流：

- 一份完整的 III 期临床方案，需要 `trial-design`、`parkinson-clinical`、`trial-statistics`、`clinical-ops` 协作完成
- 一次 IND 申报准备，需要 `toxicology`、`pharmacology`、`chemistry`、`drug-registration` 齐力推进
- 一项文献荟萃分析，需要 `ov-retriever`、`literature-analyzer`、`data-extractor`、`report-writing` 流水线运转

---

## 团队成员（Sub-Agents）

### 战略层

| Agent | 职责 |
|-------|------|
| `cmo-gpl` | **首席医学官 / 全球项目负责人**：临床开发策略、获益-风险评估、阶段推进决策、跨职能对齐 |
| `gpm` | **全球项目经理**：整合开发计划（IDP）、关键路径分析、风险登记册、里程碑规划（IND/EOP2/NDA）|

### 临床科学层

| Agent | 职责 |
|-------|------|
| `trial-design` | **临床试验设计专家**：方案撰写、随机化与盲法设计、终点选择、适应性设计（ICH E6/E8/E9/E10） |
| `parkinson-clinical` | **帕金森病临床专家**：PD 病理、分期、评分量表（MDS-UPDRS、PDQ-39）、生物标志物、SoC |
| `trial-statistics` | **临床统计学家**：样本量计算、统计分析计划（SAP）、多重性控制、期中分析、MMRM/Cox 模型 |
| `bioinformatics` | **生物信息学专家**：基因组学、生物标志物策略、伴随诊断（CDx）、NGS 分析、多组学 |

### 运营与质量层

| Agent | 职责 |
|-------|------|
| `clinical-ops` | **临床运营专家**：中心选择、CRO 管理、患者入组、风险监查（RBM/ICH E6(R2)）、IMP 供应链 |
| `quality-control` | **质量与合规专家**：GCP/GLP/GMP 审计、CAPA、TMF 管理、监管检查准备 |
| `data-management` | **临床数据管理专家**：CRF 设计、CDISC（CDASH/SDTM/ADaM）、EDC、医学编码（MedDRA/WHODrug）|

### 药学与非临床层

| Agent | 职责 |
|-------|------|
| `pharmacology` | **药理学专家**：PK/PD 建模、ADME、DDI 评估、首次人体剂量选择、暴露-效应分析 |
| `toxicology` | **毒理学专家**：GLP 毒理研究设计、遗传毒性、NOAEL/MABEL 确定、ICH S 系列指南 |
| `chemistry` | **CMC 专家**：药物物质/制剂开发、分析方法验证、稳定性研究（ICH Q 系列）、CTD 第 3 模块 |
| `drug-registration` | **法规事务专家**：IND/NDA/BLA/MAA 申报策略、FDA/EMA/NMPA 路径规划、突破性疗法认定 |

### 知识管理层

| Agent | 职责 |
|-------|------|
| `literature-analyzer` | **文献分析专家**：单篇文献深度解读、研究设计评估、结论有效性分析 |
| `data-extractor` | **数据提取专家**：从文献中提取结构化数值数据、构建跨研究对比表格 |
| `ov-retriever` | **知识库检索专家**：基于 OpenViking 的语义检索，从已索引文献库中召回相关段落 |
| `report-writing` | **临床文件撰写专家**：CSR（ICH E3）、研究者手册（IB）、方案摘要、监管简报文件 |

---

## 快速开始

### 配置

1. **克隆仓库**

   ```bash
   git clone <repository-url>
   cd deerflow-gpt-team
   ```

2. **生成本地配置文件**

   在项目根目录执行：

   ```bash
   make config
   ```

3. **配置模型**

   编辑 `config.yaml`，定义要使用的 LLM：

   ```yaml
   models:
     - name: gpt-4o
       display_name: GPT-4o
       use: langchain_openai:ChatOpenAI
       model: gpt-4o
       api_key: $OPENAI_API_KEY
       max_tokens: 4096
       temperature: 0.7

     - name: gpt-4o-mini
       display_name: GPT-4o Mini
       use: langchain_openai:ChatOpenAI
       model: gpt-4o-mini
       api_key: $OPENAI_API_KEY

     - name: openrouter-claude-3-7-sonnet
       display_name: Claude 3.7 Sonnet (OpenRouter)
       use: langchain_openai:ChatOpenAI
       model: anthropic/claude-3-7-sonnet
       api_key: $OPENROUTER_API_KEY
       base_url: https://openrouter.ai/api/v1
   ```

   通过 `langchain_openai:ChatOpenAI` + `base_url` 可以对接任何 OpenAI 兼容网关（OpenRouter、Azure OpenAI、本地 Ollama 等）。

4. **配置 API Key**

   编辑项目根目录的 `.env` 文件：

   ```bash
   OPENAI_API_KEY=your-openai-api-key
   TAVILY_API_KEY=your-tavily-api-key    # 网络搜索（可选）
   OPENROUTER_API_KEY=your-key           # 如使用 OpenRouter
   ```

### 运行应用

#### 方式一：Docker（推荐）

```bash
make docker-init    # 首次运行：拉取 sandbox 镜像
make docker-start   # 启动所有服务
```

访问地址：http://localhost:2026

生产模式：

```bash
make up     # 构建镜像并启动全部生产服务
make down   # 停止并移除容器
```

#### 方式二：本地开发

1. **检查依赖环境**：
   ```bash
   make check  # 校验 Node.js 22+、pnpm、uv、nginx
   ```

2. **安装依赖**：
   ```bash
   make install
   ```

3. **（可选）预拉取 sandbox 镜像**：
   ```bash
   make setup-sandbox
   ```

4. **启动所有服务**：
   ```bash
   make dev
   ```

5. **访问地址**：http://localhost:2026

> 在 Windows 上请使用 Git Bash 运行本地开发流程。

### 进阶配置

#### Sandbox 模式

NextTask 支持三种 Sandbox 执行模式：

- **本地执行**：直接在宿主机运行 Agent 代码
- **Docker 执行**：在隔离的 Docker 容器中运行
- **Docker + Kubernetes**：通过 provisioner 服务在 K8s Pod 中运行

配置方法见 [Sandbox 配置指南](backend/docs/CONFIGURATION.md#sandbox)。

#### MCP Server

NextTask 支持通过 MCP Server 扩展 Agent 工具集，支持 HTTP/SSE 传输方式，并内置 OAuth token 流程（`client_credentials`、`refresh_token`）。

详细说明见 [MCP Server 指南](backend/docs/MCP_SERVER.md)。

#### IM 渠道

NextTask 支持从即时通讯应用直接向团队发送任务，无需公网 IP。

| 渠道 | 传输方式 | 上手难度 |
|------|----------|----------|
| Telegram | Bot API（long-polling） | 简单 |
| Slack | Socket Mode | 中等 |
| Feishu / Lark | WebSocket | 中等 |

**`config.yaml` 配置示例：**

```yaml
channels:
  langgraph_url: http://localhost:2024
  gateway_url: http://localhost:8001

  # 全局 session 默认值
  session:
    assistant_id: lead_agent
    config:
      recursion_limit: 100
    context:
      thinking_enabled: true
      is_plan_mode: false
      subagent_enabled: true     # 开启 Sub-Agent 协作

  telegram:
    enabled: true
    bot_token: $TELEGRAM_BOT_TOKEN
    allowed_users: []

  slack:
    enabled: true
    bot_token: $SLACK_BOT_TOKEN
    app_token: $SLACK_APP_TOKEN
    allowed_users: []

  feishu:
    enabled: true
    app_id: $FEISHU_APP_ID
    app_secret: $FEISHU_APP_SECRET
```

在 `.env` 中设置对应 token：

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
FEISHU_APP_ID=cli_xxxx
FEISHU_APP_SECRET=your_app_secret
```

**渠道内可用命令：**

| 命令 | 说明 |
|------|------|
| `/new` | 开启新对话 |
| `/status` | 查看当前 thread 信息 |
| `/models` | 列出可用模型 |
| `/memory` | 查看长期记忆 |
| `/help` | 查看帮助 |

**Telegram 配置**：打开 [@BotFather](https://t.me/BotFather)，发送 `/newbot`，复制 HTTP API token。

**Slack 配置**：
1. 前往 [api.slack.com/apps](https://api.slack.com/apps) 创建 App
2. 添加 Bot Token Scopes：`app_mentions:read`、`chat:write`、`im:history`、`im:read`、`im:write`、`files:write`
3. 启用 Socket Mode，生成 App-Level Token（`xapp-...`）
4. 订阅 bot events：`app_mention`、`message.im`

**Feishu / Lark 配置**：
1. 在[飞书开放平台](https://open.feishu.cn/)创建应用并启用 Bot 能力
2. 添加权限：`im:message`、`im:message.p2p_msg:readonly`、`im:resource`
3. 订阅 `im.message.receive_v1` 事件，选择**长连接**方式

#### LangSmith 链路追踪

在 `.env` 中添加以下配置即可启用全链路追踪：

```bash
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=lsv2_pt_xxxxxxxxxxxxxxxx
LANGSMITH_PROJECT=your-project-name
```

启用后，所有 LLM 调用、Agent 运行和工具执行都会记录在 LangSmith 仪表盘中。

---

## 核心能力

### Skills 与 Tools

Skills 是 NextTask 能力扩展的核心机制。每个 Skill 是一个包含 `SKILL.md` 的目录，定义了工作流、最佳实践和工具授权规则。

Skills 采用按需渐进加载，只有任务确实需要时才注入上下文，保持 token 使用高效。

内置 Skills 覆盖：研究分析、报告生成、演示文稿制作、网页生成、图像和视频生成等。

```text
skills/
├── public/                     # 内置 Skills（版本控制）
│   ├── research/SKILL.md
│   ├── report-generation/SKILL.md
│   ├── slide-creation/SKILL.md
│   └── image-generation/SKILL.md
└── custom/                     # 自定义 Skills（不纳入版本控制）
    └── your-custom-skill/SKILL.md
```

**Tools** 方面，NextTask 内置：网页搜索、网页抓取、文件操作、Bash 执行，并支持通过 MCP Server 和 Python 函数扩展自定义工具。

### Sandbox 与文件系统

每个任务运行在独立的 Docker 容器中，提供完整的文件系统隔离：

```text
/mnt/user-data/
├── uploads/          ← 上传文件
├── workspace/        ← Agent 工作目录
└── outputs/          ← 最终交付物
```

Agent 可以读写文件、执行 Bash 命令和代码、查看图片。整个执行过程可审计、隔离，不同 session 之间不会互相污染。

### Context Engineering

**隔离的 Sub-Agent Context**：每个 Sub-Agent 运行在独立的上下文中，只聚焦当前被委托的任务，不受主 Agent 或其他 Sub-Agent 上下文干扰。

**摘要压缩**：在长链路多步骤任务中，NextTask 会主动管理上下文：总结已完成子任务、将中间结果转存到文件系统、压缩暂时不重要的信息，防止上下文窗口溢出。

**并发调度**：最多 3 个 Sub-Agent 并行运行（`MAX_CONCURRENT_SUBAGENTS = 3`），单个 Sub-Agent 超时时限 15 分钟。

### 长期记忆

NextTask 跨 session 积累持久记忆，记录用户偏好、知识背景和工作习惯。记忆存储在本地，控制权始终在用户手里。

记忆系统结构：
- **User Context**：工作背景、个人偏好、当前关注点（动态摘要）
- **History**：近期记录、较早背景、长期积累
- **Facts**：离散事实，含类别（偏好/知识/背景/行为/目标）和置信度

每次对话时，Top 15 条最相关的 facts 和上下文摘要会自动注入 system prompt。

---

## 推荐模型

NextTask 对任何实现了 OpenAI 兼容 API 的 LLM 均可接入。以下能力对于临床开发类任务尤为重要：

- **长上下文窗口**（100k+ tokens）：适合方案文件阅读和多步骤分析
- **强推理能力**：适合自适应规划和复杂任务拆解
- **多模态输入**：适合图像理解（例如 DICOM 图像、数据图表）
- **稳定的 Tool Use**：适合可靠的函数调用和结构化输出

推荐：GPT-4o、Claude Sonnet/Opus、Gemini 2.5 Pro/Flash。

---

## 内嵌 Python Client

NextTask 也可以作为内嵌的 Python 库使用，不必启动完整的 HTTP 服务：

```python
from deerflow.client import DeerFlowClient

client = DeerFlowClient()

# 普通对话
response = client.chat("请为一个 PD 早期干预研究设计 II 期方案框架", thread_id="my-thread")

# 流式输出
for event in client.stream("帮我分析这篇 MDS-UPDRS 验证研究"):
    if event.type == "messages-tuple" and event.data.get("type") == "ai":
        print(event.data["content"])

# 配置与管理
models = client.list_models()         # {"models": [...]}
skills = client.list_skills()         # {"skills": [...]}
client.update_skill("research", enabled=True)
client.upload_files("thread-1", ["./protocol.pdf"])
```

所有返回 dict 的方法都与 Gateway HTTP API schema 保持一致，通过 `TestGatewayConformance` 在 CI 中持续验证。完整 API 见 `backend/packages/harness/deerflow/client.py`。

---

## 文档

- [贡献指南](CONTRIBUTING.md) — 开发环境搭建与协作流程
- [配置指南](backend/docs/CONFIGURATION.md) — 详细配置说明
- [架构概览](backend/CLAUDE.md) — 技术架构说明
- [后端架构](backend/README.md) — 后端架构与 API 参考

---

## 安全使用

NextTask 具备**系统指令执行、文件操作、业务逻辑调用**等高权限能力，默认设计为**部署在本地可信环境（仅本机 127.0.0.1 回环访问）**。

若需要跨设备或跨网络部署，必须采取以下安全措施：

- **IP 白名单**：通过 `iptables` 或硬件防火墙配置访问控制规则
- **前置身份验证**：通过 nginx 等反向代理开启强身份验证
- **网络隔离**：将 NextTask 和可信设备划分至同一专用 VLAN

---

## 参与贡献

欢迎参与贡献。开发环境、工作流和相关规范见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 许可证

本项目采用 [MIT License](./LICENSE) 开源发布。

---

## 致谢

NextTask 建立在以下开源项目的基础之上：

- **[LangChain](https://github.com/langchain-ai/langchain)**：提供 LLM 交互与 chains 支持
- **[LangGraph](https://github.com/langchain-ai/langgraph)**：支撑多 Agent 编排与复杂工作流
