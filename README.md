# MindMate — 项目地图

> Hermes Agent (Nous Research) v0.10.0 的 fork，定制为 **MindMate** 心理健康陪伴机器人。
> 上游: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
> 本 fork: [wdn0612/mindmate](https://github.com/wdn0612/mindmate)

---

## 数据流图

```
                          ┌──────────────────────────────────────────────┐
                          │           用户消息入口                        │
                          │                                              │
  Telegram 用户 ──poll──▶│  gateway/run.py  (GatewayRunner ~11K 行)      │
  Discord / Slack        │    │                                          │
  WhatsApp / Signal      │    ├─ 全局认证层 (TELEGRAM_ALLOWED_USERS)     │
  ...20+ 平台            │    ├─ 会话管理 (SessionStore, reset policy)   │
                          │    ├─ STT 语音转文字 (faster-whisper)         │
                          │    └─ 分发到对应平台 adapter                  │
                          └──────────┬───────────────────────────────────┘
                                     │ 消息事件
                                     ▼
                    ┌────────────────────────────────────────┐
                    │         AIAgent 对话循环                 │
                    │         run_agent.py (~12K 行)          │
                    │                                         │
                    │  用户消息                                 │
                    │    ▼                                     │
                    │  ┌─────────────────────────┐             │
                    │  │  prompt_builder.py       │◀── SOUL.md  │
                    │  │  组装 system prompt:     │   人格/身份   │
                    │  │  - 身份 (DEFAULT_AGENT_  │              │
                    │  │    IDENTITY)             │              │
                    │  │  - 平台提示 (PLATFORM_   │◀── skills/  │
                    │  │    HINTS)               │   技能索引    │
                    │  │  - 技能引导 (SKILLS_     │              │
                    │  │    GUIDANCE)             │              │
                    │  │  - 记忆块 (MEMORY_       │◀── memory_  │
                    │  │    GUIDANCE)             │   manager.py │
                    │  │  - 上下文文件 (AGENTS.   │              │
                    │  │    md / SOUL.md)        │              │
                    │  └──────────┬──────────────┘             │
                    │             │                              │
                    │             ▼                              │
                    │  ┌─────────────────────────┐             │
                    │  │  LLM API 调用            │             │
                    │  │  (OpenAI-compatible)    │             │
                    │  │  provider: custom/zai   │             │
                    │  │  model: glm-5.1         │             │
                    │  │  base_url: api.z.ai     │             │
                    │  └──────────┬──────────────┘             │
                    │             │ tool_call 或 text response   │
                    │             ▼                              │
                    │  ┌─────────────────────────┐             │
                    │  │  model_tools.py          │             │
                    │  │  工具编排层:              │             │
                    │  │  handle_function_call() │             │
                    │  └──────────┬──────────────┘             │
                    │             │                              │
                    │     ┌───────┴───────┬──────────┐         │
                    │     ▼               ▼          ▼         │
                    │  tools/         tools/     tools/       │
                    │  web_tools.py  terminal_  send_message_  │
                    │  (搜索/抓取)    tool.py   tool.py       │
                    │                (Shell)   (回复用户)      │
                    │  ...61 个工具模块                      │
                    └────────────────────────────────────────┘

  ══════════════════════════════════════════════════════════════

  并发 & 调度子系统:

  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  ┌──────────┐
  │ cron/       │  │ delegate_   │  │ mcp_serve.py │  │ acp_     │
  │ scheduler.  │  │ tool.py     │  │              │  │ adapter/ │
  │ py 定时任务 │  │ 子代理派发   │  │ MCP 协议桥   │  │ IDE 集成│
  │ (自然语言   │  │ (并行工作流) │  │ (Claude Code│  │ (VSCode/ │
  │  自动化)    │  │              │  │  Cursor等)  │  │  JetBrain│
  └──────┬──────┘  └──────┬──────┘  └──────┬───────┘  └────┬─────┘
         │                │                │               │
         ▼                ▼                ▼               ▼
    投递到各平台       ThreadPool       stdio JSON-RPC   ACP 协议
    (telegram/        Executor         over stdin       (agent-client-
     discord/...)                                       protocol)
```

---

## 上下游依赖

### 本项目依赖（数据来源 / 外部 API）

| 依赖 | 用途 | 认证方式 |
|------|------|----------|
| **z.ai / GLM API** | 主力 LLM (`glm-5.1`) | `GLM_API_KEY` + `OPENAI_API_KEY` (custom provider 读后者) |
| **Telegram Bot API** | 消息收发 (主平台) | `TELEGRAM_BOT_TOKEN` |
| **Exa** | AI-native 网页搜索 | `EXA_API_KEY` |
| **Firecrawl** | 网页抓取/爬取 | `FIRECRAWL_API_KEY` |
| **Parallel** | AI 网页搜索+提取 | `PARALLEL_API_KEY` |
| **FAL.ai** | 图片生成 | `FAL_KEY` |
| **Edge TTS** | 文字转语音 (免费) | 无需 key |
| **faster-whisper** | 语音转文字 (本地) | 无需 key，本地模型 |

### 谁依赖本项目（调用者 / 消费方）

| 消费者 | 通过什么接入 |
|--------|-------------|
| **Telegram 用户** | Bot polling → `gateway/run.py` → `AIAgent` |
| **IDE (VSCode/Cursor)** | `mcp_serve.py` → stdio MCP 协议 |
| **ACP 客户端 (Zed/JetBrains)** | `acp_adapter/` → agent-client-protocol |
| **Cron 定时任务** | `cron/scheduler.py` → gateway 内部调度 |
| **子代理 (delegate)** | `delegate_tool.py` → ThreadPoolExecutor 并行 |

### 内部模块依赖关系

```
gateway/run.py (网关入口)
  ├── agent/prompt_builder.py ← config/SOUL.md, skills/
  ├── agent/context_compressor.py (上下文压缩)
  ├── agent/memory_manager.py (记忆管理)
  ├── model_tools.py (工具编排)
  │   ├── tools/registry.py (工具注册中心)
  │   └── toolsets.py (工具集定义)
  ├── hermes_state.py (SessionDB, SQLite FTS5)
  └── gateway/platforms/ (20+ 平台适配器)
        ├── telegram.py (主部署平台)
        ├── discord.py, slack.py, whatsapp.py ...
        └── base.py (抽象基类)

hermes_cli/main.py (CLI 入口)
  ├── cli.py (交互式终端 UI, ~11K 行)
  ├── hermes_cli/config.py (配置管理)
  ├── hermes_cli/auth.py (多 provider 认证)
  ├── hermes_cli/gateway.py (gateway 服务管理)
  └── hermes_cli/setup.py (初始化向导)
```

---

## 核心文件清单

### 入口 & 引擎

| 文件 | 大小 | 干什么 |
|------|------|--------|
| `hermes` | 273B | CLI 启动脚本 → `hermes_cli.main:main` |
| `run_agent.py` | 620KB | **AIAgent 对话循环核心** — 接收消息→组装prompt→调LLM→执行工具→返回结果，~12000行 |
| `cli.py` | 497KB | **HermesCLI 交互式终端** — TUI REPL、斜杠命令、富文本渲染，~11000行 |
| `gateway/run.py` | 519KB | **GatewayRunner** — 多平台消息网关总控，session 管理、认证、流式输出，~11200行 |
| `mcp_serve.py` | 31KB | MCP server — 把对话暴露为 MCP tool 给 IDE 用 |
| `rl_cli.py` | 16KB | RL 训练 CLI (Tinker + Atropos) |
| `batch_runner.py` | 56KB | 批量轨迹生成 |

### Agent 内部模块 (`agent/` — 从 run_agent.py 拆出的纯函数库)

| 文件 | 功能 |
|------|------|
| `prompt_builder.py` | System prompt 组装：身份、技能索引、记忆、上下文文件、SOUL.md 注入 |
| `context_compressor.py` | 长对话自动压缩 — 中间轮次摘要化腾出 context 空间 |
| `memory_manager.py` | 记忆系统 — 跨会话记忆检索、用户画像构建 |
| `auxiliary_client.py` | 辅助模型客户端 — vision、web_extract、approval 等子任务 |
| `tool_result_sanitizer.py` | **[MindMate]** 工具结果安全过滤 — 敏感信息脱敏 |
| `error_classifier.py` | API 错误分类 + 自动 failover (换 provider/model 重试) |
| `model_metadata.py` | 模型元数据 — context window、token 计费、provider 能力探测 |
| `credential_pool.py` | 多密钥轮转池 — 同一 provider 多个 key 自动负载均衡 |
| `skill_commands.py` / `skill_utils.py` | 技能系统 — SKILL.md 解析、条件匹配、索引构建 |

### 工具系统 (`tools/` — 61 个工具模块 + 注册中心)

| 文件 | 功能 |
|------|------|
| `registry.py` | **工具注册中心** — 每个 tool 文件 `import` 时自注册 schema+handler，AST 扫描发现 |
| `send_message_tool.py` | **回复用户** — 所有平台的消息发送统一入口 (69KB) |
| `terminal_tool.py` | **Shell 命令执行** — 支持 local/docker/modal/ssh/singularity 后端 (87KB) |
| `web_tools.py` | **网页浏览/搜索** — Exa + Firecrawl + Parallel (87KB) |
| `browser_tool.py` | **浏览器自动化** — Browserbase 云端浏览器 (100KB) |
| `delegate_tool.py` | **子代理派发** — spawn 隔离并行工作流 (89KB) |
| `code_execution_tool.py` | **代码执行** — 沙箱内跑 Python (62KB) |
| `file_operations.py` | **文件读写** — 安全路径检查 (50KB) |
| `memory_tool.py` | **记忆读写** — 跨会话持久记忆 (23KB) |
| `skills_tool.py` / `skills_hub.py` | **技能管理** — 安装/搜索/加载 SKILL.md |
| `mcp_tool.py` | **MCP 工具桥接** — 连接外部 MCP server (105KB) |
| `tts_tool.py` | **语音合成** — Edge TTS (免费) / ElevenLabs (58KB) |
| `voice_mode.py` | **语音模式** — 全双工语音对话 (38KB) |
| `image_generation_tool.py` | **图片生成** — FAL.ai (38KB) |
| `transcription_tools.py` | **语音转文字** — Groq/OpenAI/本地 whisper (32KB) |
| `approval.py` | **命令审批** — 危险操作需用户确认 (41KB) |

### Gateway 平台适配器 (`gateway/platforms/` — 21 个平台)

| 文件 | 平台 |
|------|------|
| `telegram.py` | **Telegram (主力)** — polling/webhook 双模式，139KB |
| `discord.py` | Discord — 文字/语音/线程/reaction，164KB |
| `slack.py` | Slack — Socket Mode + Web API |
| `whatsapp.py` | WhatsApp — Baileys bridge |
| `feishu.py` | 飞书/Lark — 192KB |
| `wecom.py` / `wecom_callback.py` | 企业微信 — bot + callback 双模式 |
| `weixin.py` | 微信 (个人) — iLink Bot API |
| `matrix.py` | Matrix — E2EE 加密支持 |
| `signal.py` | Signal — signal-cli HTTP bridge |
| `api_server.py` | HTTP API Server — RESTful 接口，112KB |
| `webhook.py` | 通用 Webhook 接收 |
| `dingtalk.py` | 钉钉 |
| `email.py` | Email — IMAP/SMTP |
| `bluebubbles.py` | iMessage — BlueBubbles server |
| `homeassistant.py` | Home Assistant |
| `mattermost.py` | Mattermost |
| `sms.py` | SMS — Twilio |
| `qqbot.py` | QQ 官方 Bot v2 |

### 配置 & 常量

| 文件/路径 | 用途 |
|-----------|------|
| `config/SOUL.md` | **MindMate 人格定义** — 心理健康陪伴身份、语气、危机协议 |
| `pyproject.toml` | Python 包定义 — `hermes-agent` v0.10.0, >=3.11 |
| `.env.example` | 环境变量完整模板 (401行, 30+ provider) |
| `cli-config.yaml.example` | YAML 配置完整模板 (959行) |
| `hermes_constants.py` | 路径常量 — `get_hermes_home()` (默认 `~/.hermes`) |
| `Dockerfile` | 容器构建 — Debian 13 + uv + Playwright |
| `gateway/config.py` | GatewayConfig 数据类 — 平台配置、session 策略、流式输出 |
| `gateway/session.py` | SessionStore — 持久化会话存储 |
| `gateway/delivery.py` | DeliveryRouter — cron 输出路由到各平台 |

### 技能系统 (`skills/` — 27 类内置技能 + `optional-skills/`)

| 目录 | 说明 |
|------|------|
| `skills/creative/` | 创意: ASCII art, p5.js, manim 视频, 像素画, 宝宝漫画... |
| `skills/software-development/` | 软件开发: TDD, 系统调试, code review, 计划... |
| `skills/productivity/` | 效率: Notion, Linear, Google Workspace, OCR... |
| `skills/research/` | 研究: arXiv, blogwatcher, 论文写作... |
| `skills/github/` | GitHub: PR workflow, code review, issue 管理... |
| `skills/media/` | 媒体: YouTube, GIF, 音乐识别... |
| `skills/mlops/` | ML/OPS: PyTorch FSD, Whisper, Stable Diffusion, Qdrant, FAISS... |
| `optional-skills/` | 可选技能: blockchain, bioinformatics, 3D打印... (190 files) |

### 其他子系统

| 目录/文件 | 说明 |
|-----------|------|
| `cron/` | 内置 cron 调度器 — 自然语言定时任务，投递到任意平台 |
| `plugins/` | 插件系统 — disk-cleanup, memory (honcho/mem0/holographic)... |
| `environments/` | RL 训练环境 — Atropos, SWE bench, web research |
| `ui-tui/` | Web Terminal UI — React/Ink 前端 + tui_gateway/ Python 后端 |
| `web/` | Web Dashboard — Vite + React, 打包进 `hermes_cli/web_dist/` |
| `website/` | 文档站点源码 (VitePress) |
| `tests/` | 测试套件 — 726 个测试文件 |
| `霺霺/` | **[MindMate 自有目录]** — 项目级笔记/规划 |

---

## 配置项

### 关键环境变量 (生产部署)

```bash
# === 必需 ===
TELEGRAM_BOT_TOKEN=          # Telegram bot token (@BotFather)
TELEGRAM_ALLOWED_USERS=839436702,738082744,6872598364  # 白名单用户 ID
OPENAI_API_KEY=               # GLM API key (custom provider 读此变量)
GLM_API_KEY=                  # 同上 (z.ai 的 key)

# === 模型配置 (config.yaml) ===
# model.default: glm-5.1
# model.provider: custom
# model.base_url: https://api.z.ai/api/paas/v4

# === 可选工具 API ===
EXA_API_KEY=                  # 网页搜索
FIRECRAWL_API_KEY=            # 网页抓取
FAL_KEY=                     # 图片生成

# === Gateway 行为 ===
GATEWAY_ALLOW_ALL_USERS=false # 全局开关 (false=白名单)
HERMES_HUMAN_DELAY_MODE=natural  # 回复拟人延迟
SESSION_IDLE_MINUTES=1440    # 会话超时 (24h)
```

### 运行时目录结构 (`~/.hermes/`)

```
~/.hermes/
├── config.yaml          # 主配置 (模型/provider/平台/压缩)
├── .env                 # 环境变量 (API keys 等)
├── SOUL.md              # → symlink/config 指向 config/SOUL.md
├── sessions/            # 会话存储 (SQLite)
├── logs/                # 运行日志
│   ├── agent.log
│   └── errors.log
├── skills/              # 用户安装的技能
├── optional-skills/     # 可选技能
├── cron/                # cron 任务定义
└── gateway.json         # legacy 配置 (已迁移到 config.yaml)
```

---

## 启动方式

### 本地开发

```bash
# 1. 创建 venv + 安装依赖
uv venv venv --python 3.11
uv pip install -e ".[all]" --python venv/bin/python

# 2. 交互式 CLI (终端聊天)
source venv/bin/activate
python cli.py
# 或: hermes chat

# 3. 启动 Gateway (消息机器人)
python -m gateway.run
# 或: hermes gateway          # 前台运行
# 或: hermes gateway start    # 后台服务

# 4. MCP Server (给 IDE 用)
python mcp_serve.py
# 或: hermes mcp serve
```

### Docker 部署

```bash
docker build -t mindmate .
docker run -d \
  -v mindmate-data:/opt/data \
  -e TELEGRAM_BOT_TOKEN=xxx \
  -e OPENAI_API_KEY=xxx \
  --name mindmate mindmate
```

### 生产服务器 (当前部署 — 腾讯云 Lighthouse)

```bash
# VPS 上的启动命令 (nohup)
export TELEGRAM_BOT_TOKEN="xxx"
export TELEGRAM_ALLOWED_USERS="839436702,738082744,6872598364"
export OPENAI_API_KEY="xxx"
export GLM_API_KEY="$OPENAI_API_KEY"

cd /home/ubuntu/.hermes/hermes-agent
nohup venv/bin/python -m gateway.run > /dev/null 2>&1 &

# 日志位置:
tail -f /root/.hermes/logs/agent.log
tail -f /root/.hermes/logs/errors.log
```

---

## MindMate 定制点 (vs upstream Hermes)

| 定制 | 位置 | 说明 |
|------|------|------|
| `[MindMate]` 安全标记 | `gateway/run.py` ~L2988 | 全局认证层的 MindMate 身份标识 |
| `tool_result_sanitizer.py` | `agent/tool_result_sanitizer.py` | 工具结果安全过滤 (341行服务器版) |
| `SOUL.md` 人格 | `config/SOUL.md` | 心理健康陪伴人格 — 冷静、好奇、尊重、在场 |
| Telegram 自定义菜单 | `gateway/platforms/telegram.py` ~L868 | 6 条 MindMate 专属命令 (start/new/help/model/stop/status) |
| 白名单访问控制 | `TELEGRAM_ALLOWED_USERS` | 3 人白名单 (owner + Daini + Haoran Luo) |
| `霺霺/` 目录 | 项目根目录 | 项目级自有笔记/规划空间 |

---

## 架构关键数字

| 维度 | 数值 |
|------|------|
| Python 版本 | >= 3.11 |
| 支持平台数 | 21 (telegram/discord/slack/whatsapp/飞书/企微/微信/...) |
| 内置工具数 | 61 个工具模块 |
| 内置技能类 | 27 类 (+ optional ~40) |
| LLM Provider | 20+ (OpenRouter/Anthropic/OpenAI/z.ai/GLM/Kimi/...) |
| 核心代码行数 | ~150K 行 Python (500 .py 文件) |
| 测试文件数 | 726 |
| 包大小 (pyproject) | `hermes-agent` v0.10.0 |
