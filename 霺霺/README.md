# 🦊 霺霺 & 沈时飖 — Mindmate 部署记录

> HACHOTHON 比赛项目 · 腾讯云 Lighthouse 部署全流程

---

## 一、项目信息

| 项目 | 值 |
|---|---|
| **源项目** | [wdn0612/mindmate](https://github.com/wdn0612/mindmate) (Hermes Agent v0.10.0) |
| **Fork 地址** | [yunalinzw-ssy/mindmate](https://github.com/yunalinzw-ssy/mindmate) |
| **版本** | v0.10.0 (2026.4.16) |
| **技术栈** | Python 3.11+ / TypeScript / uv (包管理) / Docker |

## 二、服务器配置

| 项目 | 值 |
|---|---|
| **云服务商** | 腾讯云 Lighthouse（轻量应用服务器） |
| **地域** | 新加坡 (ap-singapore) |
| **实例 ID** | `lhins-nt8knmsl` |
| **实例名** | Hermes Agent-nrKt |
| **公网 IP** | 43.156.253.62 |
| **套餐** | Starter — 2 核 CPU / 2GB 内存 / 40GB SSD / 512GB 月流量 / 峰值 200Mbps |
| **操作系统** | Ubuntu (Debian Trixie based, 内核 6.8) |
| **镜像** | Hermes Agent v0.10.0 预置镜像 |
| **到期时间** | 2026-05-29（1 个月，比赛用） |

### 为什么选 Lighthouse

Mindmate 是 Python Agent 后端项目，需要：
- ✅ 完整运行时环境（Python + 长驻进程）
- ✅ Docker 支持
- ✅ 网关端口开放（Telegram/Discord 等）
- ✅ Cron 定时任务
- ❌ EdgeOne Pages = 只能托管静态资源，跑不了后端
- ❌ Cloud Studio = 临时预览沙箱，有过期时间
- ❌ CloudBase = Serverless 不适合长驻 Agent 进程
- **结论：Lighthouse = 本质就是 VPS，完美匹配**

## 三、部署方式：宿主机直装（非 Docker）

Docker build 在 2G 内存机器上失败，改用宿主机直接安装，更轻量。

### 步骤记录

```bash
# 1. 安装 Docker（镜像自带但未启用）
apt-get update && apt-get install -y docker.io
systemctl start docker && systemctl enable docker

# 2. 克隆 Fork 的仓库到服务器
apt-get install -y git
git clone https://github.com/yunalinzw-ssy/mindmate.git /root/mindmate

# 3. 安装 uv 包管理器
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# 4. 创建虚拟环境 + 安装依赖
cd /root/mindmate
uv venv
source .venv/bin/activate
uv pip install -e ".[all]"

# 5. 配置 LLM Provider（智谱 GLM）
hermes config set model.provider custom
hermes config set model.base_url https://api.z.ai/api/paas/v4
hermes config set model.default glm-5.1

# 6. 写入 .env 文件
echo 'GLM_API_KEY=d3ea16b8d7ad49afafca496ea0ecbc20.5cBzyTCUQfLak33U' > .env
echo 'GLM_BASE_URL=https://api.z.ai/api/paas/v4' >> .env
```

## 四、LLM 配置

| 项目 | 值 |
|---|---|
| **Provider** | Custom（OpenAI 兼容接口） |
| **模型** | glm-5.1（智谱 GLM-5.1） |
| **Base URL** | `https://api.z.ai/api/paas/v4` |
| **API Key 来源** | [智谱 AI 开放平台](https://open.bigmodel.cn) |

> Hermes Agent 原生支持 GLM（z.ai），`.env.example` 中已有完整配置项。

## 五、Git 远程源配置

```bash
origin    → https://github.com/yunalinzw-ssy/mindmate.git   （我们的 Fork）
upstream  → https://github.com/wdn0612/mindmate.git          （朋友的源仓库）
```

### 同步上游更新

```bash
git fetch upstream
git merge upstream/main
git push origin main
```

## 六、已知问题

| 问题 | 状态 | 说明 |
|---|---|---|
| CodeBuddy Lighthouse API 无法连接实例 | ⚠️ 未解决 | TAT Agent 注册同步延迟，控制台「执行命令」可正常使用 |
| Docker build 失败（Exit Code 1） | ✅ 已绕过 | 改用宿主机直装，更轻量 |
| hermes setup 非交互式环境不可用 | ✅ 已绕过 | 控制台无 TTY，改用 `hermes config set` 手动配置 |

## 七、目录结构

```
mindmate/
├── 霺霺/                    ← 你在这里（本文件）
│   └── README.md            ← 部署全记录
├── agent/                   ← 核心 Agent 逻辑
├── skills/                  ← 技能系统（程序性记忆）
├── plugins/                 ← 插件系统
├── tools/                   ← 工具集
├── gateway/                 ← 消息网关（Telegram/Discord 等）
├── web/                     ← Web 前端
├── cron/                    ← 定时任务调度
├── docker/                  ← Docker 配置
├── .env                     ← API Key 配置（已写入）
├── pyproject.toml           ← 项目依赖定义
└── Dockerfile               ← Docker 构建文件（本次未使用）
```

## 八、时间线

| 时间 | 事件 |
|---|---|
| 2026-04-29 14:28 | 项目路径搬迁确认 skill/hook 可用 |
| 2026-04-29 14:36 | 分析朋友 GitHub 仓库 (wdn0612/mindmate) |
| 2026-04-29 14:38 | Fork 仓库 + 克隆到本地 + 配置 upstream |
| 2026-04-29 14:47 | 同步朋友最新版（+572/-56 行，7 文件） |
| 2026-04-29 14:50 | 决定使用 Tencent Lighthouse 部署方案 |
| 2026-04-29 14:55 | 选定新加坡地域 |
| 2026-04-29 15:05 | 开通 Lighthouse 实例（Starter 套餐，Hermes Agent 预置镜像） |
| 2026-04-29 15:08 | 实例运行中，IP: 43.156.253.62 |
| 2026-04-29 15:19 | 安装 Docker 29.1.3 |
| 2026-04-29 15:25 | Git clone Fork 到服务器 /root/mindmate |
| 2026-04-29 15:40 | 安装 uv 0.11.8 + pip 依赖全部完成 |
| 2026-04-29 15:50 | 配置智谱 GLM API Key + 模型设置完成 |
| 2026-04-29 15:52 | Hermes Agent 启动验证通过 ✅ |

---

*📅 最后更新：2026-04-29 · 由 沈时飖 & 霺霺 共同完成*
*🏷️ HACHOTHON 比赛 · DAINI Project*
