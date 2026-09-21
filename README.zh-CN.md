[English](README.md) | 简体中文

# 一键启动 Laya · One-Click Laya

> **本地运行的 System-1 决策模型，一条命令在三端跑起来。** 无需懂 Python / PyTorch / 模型部署，自带 Web 管理面板管理服务。

[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-blue)](https://github.com/rexleimo/laya-setup)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](https://github.com/rexleimo/laya-setup)
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/rexleimo/laya-setup)
[![Stars](https://img.shields.io/github/stars/rexleimo/laya-setup?style=social)](https://github.com/rexleimo/laya-setup)

**关键词：** *Laya · 本地决策模型 · System-1 AI · 一键启动 · 自托管 · 本地推理 · TypeSafe 兼容 · Agent Skill · 校准概率分类 · 不生成文本*

---

## 这是什么？

**laya-setup** 是 [Laya](https://github.com/NandhaKishorM/laya) 本地决策服务的**一键启动工具包**。

Laya 是一个**本地运行的 System-1 决策模型**：你给它一段内容（文本 / 邮件 / 工单 / JSON）加上一组**类型化问题**（分类 choice / 是否 noul / 评分 score），它用**单次前向传播**返回**带校准概率**的答案——它**不生成文本**，只做判断，CPU 上约 35–400ms 出结果。

这个仓库把这些全部自动化：**建虚拟环境 → 装依赖 → 下载模型权重 → 启动 API 服务 → 图形化管理**，一条命令搞定，Windows / Linux / macOS 通用。

## 解决什么痛点？

| 痛点 | 一键启动如何解决 |
|------|------------------|
| 跑个本地模型要懂 Python/venv/torch/模型部署 | 全部自动，`start.bat` / `./start.sh` 一条命令 |
| 下载 HuggingFace 权重国内慢 / 失败 | 默认国内镜像，海外可切官方源，附手动下载引导 |
| 起停服务、看状态要敲命令 | 自带 Web 管理面板，点按钮启停、看健康状态、看日志 |
| 想让 AI Agent（Claude Code/Cline/Codex）调用 | 提供标准 Agent Skill，智能体读一个文件就会调；本地 HTTP 直连，无需任何桥 |
| 已有 TypeSafe SDK 工具链 | `TYPESAFE_BASE_URL` 指过来即可无缝切换，零改代码 |
| 数据不能出本机 | 完全本地推理，隐私数据不出境 |

## 特性

- **真·一键**：首次自动搭环境、下权重、起服务；之后直接启动
- **三端通用**：Windows / Linux / macOS 逻辑一致，自动处理平台差异
- **Web 管理面板**：浏览器打开，零额外依赖，启停服务 / 看状态 / 下模型 / 看日志
- **双接口**：Laya 原生 `/predict` + TypeSafe 兼容 `/v1/systemone`
- **Agent Skill**：内置 `skills/laya/SKILL.md`，Claude Code / Cline / Codex 等智能体加载即会用
- **下载无忧**：国内镜像默认，海外官方源，ModelScope 备选，失败给手动指引
- **本地隐私**：全流程本机推理，适合处理敏感工单 / 邮件 / 内部数据

---

## 快速开始

入口文件三端不同，逻辑完全一致：

| 平台 | 首次 / 日常启动 | 管理面板 |
|------|----------------|---------------------|
| **Windows** | `start.bat` | `start-gui.bat` |
| **Linux / macOS** | `./start.sh` | `./start-gui.sh` |

> `start-gui.*` 会在浏览器打开管理面板（等价于 `start.bat panel`）。

```bash
# Linux / macOS 首次需给执行权限
chmod +x start.sh
./start.sh
```

首次运行会自动：创建 `.venv` → 安装依赖与 PyTorch → 下载 english 权重（约 840MB）→ 启动 API（`http://127.0.0.1:8399`）。

**前置要求：** Python 3.9+ 或 [uv](https://astral.sh/uv)（任选其一，装 uv 更快）。首次运行按 `bin/uv.exe` → 系统 `uv` → `python -m venv` 的顺序自动建环境。Windows 若想完全免 Python，可把 uv 可执行文件放到 `bin/`。

### 命令参考

底层都由跨平台脚本 `onekey.py` 驱动，三端可直接用 Python 调用：

```bash
python onekey.py            # 首次：建 venv、装依赖、下 english 权重、起 API
python onekey.py server     # 以后：直接起 API
python onekey.py gpu        # CUDA 版 torch（Windows/Linux；macOS 自动用 CPU/MPS）
python onekey.py stop       # 停止服务
python onekey.py status     # 查看状态 + 健康检查
python onekey.py detach     # 后台方式起服务（不占用当前终端）
python onekey.py doctor     # 环境预检：Python/uv/venv/磁盘/模型/下载源
python onekey.py model      # 下载模型权重（--source mirror|official）
python onekey.py panel      # 打开 Web 管理面板 (gui 为别名)
python onekey.py web        # 用默认浏览器打开状态页
```

> `onekey.py` 自动处理平台差异：venv 路径（`Scripts\` vs `bin/`）、`uv` 查找（内置 / 系统 / 回退 `python -m venv`）、torch 安装源、进程停止方式（Windows `taskkill` vs Unix 信号）。

### 下载源（国内 / 海外）

onekey **不自动探测区域**，而是引导你按网络选择：

- **国内用户**（默认，速度快）：镜像源 `hf-mirror.com`
- **海外用户**：官方源 `huggingface.co`（`--source official` 或设 `HF_ENDPOINT`）
- **手动下载**：国内镜像 / 官方 / [ModelScope](https://www.modelscope.cn/models/convaiinnovations/laya) 下载后放入 `models/laya/`

下载前可先 `python onekey.py doctor` 预检环境与磁盘空间（模型约 840MB）。

### 管理面板（Web GUI）

```bash
start-gui.bat          # Windows：自动打开浏览器面板
./start-gui.sh         # Linux / macOS
python onekey.py panel # 或任意平台直接用 Python 调用
```

`start-gui` 会在本地起一个管理服务（`http://127.0.0.1:8398`）并**自动用浏览器打开**，可**启动/停止服务、查看健康与模型状态、下载权重、安装 GPU 依赖、环境自检，并实时查看日志**。

> 用浏览器面板是因为不少 Python（尤其 uv 安装的精简版）默认不带 tkinter，会导致双击 GUI 毫无反应；浏览器面板跨平台 100% 可用。`python onekey.py gui` 现在也指向同一个 Web 面板。

### 在线试用（demo.html）

`demo.html` 是一个交互式体验页：左侧填入文本 + 类型化问题，点「决策」即可看到分类 / 评分 / 概率结果。

页面为**纯前端演示模式**：结果由浏览器按关键词规则本地模拟，**不依赖、也不连接任何服务**，
双击即可打开（或挂在任意静态托管上），用来体验 Laya 的调用与返回结构。
要接真实模型，在本地启动服务后调用 `POST http://127.0.0.1:8399/predict` 即可（见 LAYA.md）。

---

## HTTP 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 存活 + 已加载/可用的 checkpoint |
| GET | `/v1/models` | 模型列表（`jev-latest` 即 english） |
| POST | `/predict` | Laya 原生：`{"state","questions","model"?}` |
| POST | `/v1/systemone` | TypeSafe 兼容：设 `TYPESAFE_BASE_URL=http://127.0.0.1:8399` 即可对接 |
| GET | `/` | 带 curl 示例的状态页 |

```bash
curl -s http://127.0.0.1:8399/predict -H "Content-Type: application/json" -d @- <<'EOF'
{"state":"We were billed twice for March. Please refund the duplicate or we will cancel.",
 "questions":{"department":{"type":"choice","instructions":"Which team?","criteria":{"billing":"refunds","technical":"bugs","sales":"pricing","other":"misc"}},
              "urgency":{"type":"score","instructions":"How urgent?","criteria":["none","soon","blocking"]},
              "churn_risk":{"type":"noul","instructions":"Threatens to cancel?"}}}
EOF
```

Agent 接入细节见 [`LAYA.md`](LAYA.md)。

## 给 AI Agent 的 Skill（Claude Code / Cline / Codex …）

本地决策不需要 MCP 服务——Agent 在本机直接 HTTP 调用即可。仓库内置标准技能文件
[`skills/laya/SKILL.md`](skills/laya/SKILL.md)，任何支持 Agent Skills 的智能体加载后
就会正确调用（探活 → `POST /predict` → 解读 choice / score / noul 的概率答案）。

### 方式一：把提示词丢给大模型（推荐）

既然用着大模型，就让大模型自己干活——把下面这段原样粘给你的 Agent 即可：

```text
请帮我安装 Laya 本地决策技能：
1. 下载 https://raw.githubusercontent.com/rexleimo/laya-setup/main/skills/laya/SKILL.md
2. 保存为 .claude/skills/laya/SKILL.md（目录不存在就创建；如果你不是 Claude Code，
   就把这份内容放进你自己的技能/规则机制，比如 CLAUDE.md 或系统提示）
3. 通读之后向我复述：你会在哪些场景用它、choice/score/noul 三种题型分别怎么调
4. 顺手请求 http://127.0.0.1:8399/health，告诉我 Laya 服务现在是否在运行
```

Agent 会自己下载、自己安装、自己学会，还顺手帮你确认服务状态——全程只需粘贴一次。

### 方式二：手动下载安装

**Claude Code（项目级）** —— 在你的项目根目录执行：

```bash
# macOS / Linux / Git Bash
mkdir -p .claude/skills/laya
curl -sL -o .claude/skills/laya/SKILL.md \
  https://github.com/rexleimo/laya-setup/raw/main/skills/laya/SKILL.md
```

```powershell
# Windows PowerShell
New-Item -ItemType Directory -Force .claude\skills\laya | Out-Null
Invoke-WebRequest https://github.com/rexleimo/laya-setup/raw/main/skills/laya/SKILL.md `
     -OutFile .claude\skills\laya\SKILL.md
```

装到全局（所有项目可用）则放进 `~/.claude/skills/laya/`。装好后 Agent 会按需自动加载；
也可以直接对它说「读一下 `.claude/skills/laya/SKILL.md`」立即生效。

**其他 Agent / 手动方式**：浏览器打开
[SKILL.md 全文](https://github.com/rexleimo/laya-setup/blob/main/skills/laya/SKILL.md)，
整份复制进 Agent 的系统提示或规则文件（`CLAUDE.md` / `.cursorrules` / Cline 规则等）即可。

> 下载版是"即丢即用"的单文件 Skill：无需注册、无需联网服务本身之外的东西；
> 唯一前提是本机 Laya 服务在运行（没运行就 `python onekey.py run` 或面板点「启动服务」）。

深入字段与模型变体见 [LAYA.md](LAYA.md)。

## 模型变体

```bash
python onekey.py model                                   # english（默认，~840MB）
python download_model.py --variant multilingual          # 多语言（~650MB）
python download_model.py --variant typed-decisions       # 专用决策头（~840MB）
```

非拉丁文本自动路由到 multilingual（若已下载），否则走 english。

---

## 常见问题（FAQ）

**Q：需要 GPU 吗？** 不需要。CPU 即可运行（单次约 35–400ms）。需要更快可用 `onekey.py gpu`（NVIDIA CUDA）；macOS 用 CPU/MPS。

**Q：模型权重多大？从哪里下？** 约 840MB。默认走国内镜像 `hf-mirror.com`，海外切官方 `huggingface.co`，也可从 ModelScope 手动下载放入 `models/laya/`。

**Q：和调用云端大模型比有什么不同？** Laya 不生成文本，只对类型化问题返回**带校准概率**的判断，适合分流/分诊/护栏等决策场景；且完全本地，隐私数据不出本机。

**Q：能接入我现有的工具链吗？** 可以。HTTP 端设 `TYPESAFE_BASE_URL=http://127.0.0.1:8399` 即可作为 TypeSafe 兼容替代；AI Agent 则加载内置的 `skills/laya/SKILL.md` 即可学会调用。

**Q：服务怎么停？** `python onekey.py stop`，或前台运行时按 `Ctrl+C`，或在管理面板点「停止服务」。

---

## 关于 · 梦兽编程

**这个项目由 [梦兽编程（RexAI）](https://rexai.top) 维护。** 我们在博客与产品站持续写 Agent 工程实践、开源我们的自研项目——如果这个仓库对你有用，欢迎关注：

**博客 & 产品站：[rexai.top](https://rexai.top)** · **GitHub：[@rexleimo](https://github.com/rexleimo)** · **全部作品：[rexai.top/products](https://rexai.top/products/)**

几个有代表性的开源作品：

| 作品 | 一句话介绍 |
|---|---|
| [HNO](https://github.com/rexleimo/agno-Go) | Go 原生多 Agent 框架，Agent / Team / Workflow 共享组件，性能可复现 |
| [AIOS](https://github.com/rexleimo/aios) | Local-First Agent 工作流层，给 codex / claude / opencode 加记忆、团队与验证 |
| [rex-harness](https://github.com/rexleimo/rex-harness) | AIOS 底层的工作流内核（Observation → Fact → Capability → Command → Evidence） |
| [Hermes Console](https://github.com/rexleimo/hermes-setup) | Hermes Agent 可视化运维中台：装 Agent、起 Gateway、配模型与渠道，全程免 SSH |
| [一览 Yilan](https://github.com/rexleimo/yilang-browser) | iOS 原生风格的移动浏览器，以书签管理为核心，隐私优先、免费无登录 |
| [REX-GAME](https://game.rexai.top) | 可玩民俗文化馆：甲骨文、二十四节气、山海拾遗，即开即玩 |

---

## Star 历史 & 致谢

如果它帮你省去了搭环境的麻烦，欢迎点个 Star。模型与推理来自 [NandhaKishorM/laya](https://github.com/NandhaKishorM/laya)，本仓库专注于**跨平台一键启动与运维**。

**Topics:** `laya` `local-ai` `decision-model` `system-1` `one-click` `self-hosted` `typesafe` `agent-skills` `on-premise` `llm-alternative` `python` `cross-platform`
