# One-Click Laya

English | [简体中文](README.zh-CN.md)

> **A System-1 decision model that runs locally — up and running on all three platforms with one command.** No Python / PyTorch / model-deployment knowledge required, with a built-in web panel to manage the service.

[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-blue)](https://github.com/rexleimo/laya-setup)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](https://github.com/rexleimo/laya-setup)
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/rexleimo/laya-setup)
[![Stars](https://img.shields.io/github/stars/rexleimo/laya-setup?style=social)](https://github.com/rexleimo/laya-setup)

**Keywords:** *Laya · local decision model · System-1 AI · one-click setup · self-hosted LLM alternative · on-premise inference · TypeSafe-compatible API · agent skill · calibrated classification · no text generation.*

---

## What is this?

**laya-setup** is a **one-click launcher toolkit** for the [Laya](https://github.com/NandhaKishorM/laya) local decision service.

Laya is a **System-1 decision model that runs entirely on your machine**: you give it some content (text / email / ticket / JSON) plus a set of **typed questions** (choice / noul (yes-no) / score), and a **single forward pass** returns answers with **calibrated probabilities** — it **never generates text**, it only judges. ~35–400 ms per call on CPU.

This repo automates the whole thing: **create venv → install dependencies → download model weights → start the API → manage it in a web panel**, all in one command, on Windows / Linux / macOS.

## The pain points it solves

| Pain point | How one-click Laya solves it |
|------|------------------|
| Running a local model means Python/venv/torch/deployment | All automated — `start.bat` / `./start.sh`, one command |
| HuggingFace downloads slow or failing | Mirror by default, official source switchable, manual-download guidance on failure |
| Starting/stopping and checking status from the CLI | Built-in web panel: click to start/stop, view health, tail logs |
| Want AI agents (Claude Code/Cline/Codex) to call it | Standard Agent Skill included — agents learn from one file; direct local HTTP, no bridge needed |
| Already on the TypeSafe SDK toolchain | Point `TYPESAFE_BASE_URL` here for a drop-in switch, zero code changes |
| Data must never leave the machine | 100% local inference — sensitive data stays on-device |

## Features

- **Truly one-click**: first run sets up the environment, downloads weights and starts the service; every run after that just starts it
- **Three platforms**: Windows / Linux / macOS share one logic; platform differences handled automatically
- **Web management panel**: opens in your browser, zero extra dependencies — start/stop, status, model download, live logs
- **Dual API**: Laya-native `/predict` + TypeSafe-compatible `/v1/systemone`
- **Agent Skill**: ships with `skills/laya/SKILL.md` — Claude Code / Cline / Codex agents learn it by loading one file
- **Hassle-free downloads**: mirror by default (fast in China), official source overseas, ModelScope fallback, manual guidance on failure
- **Local privacy**: inference never leaves the machine — fits sensitive tickets / emails / internal data

---

## Quick start

The entry script differs per platform, the logic is identical:

| Platform | First run / daily start | Management panel |
|------|----------------|---------------------|
| **Windows** | `start.bat` | `start-gui.bat` |
| **Linux / macOS** | `./start.sh` | `./start-gui.sh` |

> `start-gui.*` opens the management panel in your browser (equivalent to `start.bat panel`).

```bash
# Linux / macOS: allow execution once
chmod +x start.sh
./start.sh
```

The first run automatically: creates `.venv` → installs dependencies incl. PyTorch → downloads the english weights (~840MB) → starts the API (`http://127.0.0.1:8399`).

**Requirements:** Python 3.9+ or [uv](https://astral.sh/uv) (either one; uv is faster). On first run the environment is created in the order `bin/uv.exe` → system `uv` → `python -m venv`. On Windows you can go fully Python-free by dropping a uv executable into `bin/`.

### Command reference

Everything is driven by the cross-platform `onekey.py`, callable directly on all three platforms:

```bash
python onekey.py            # First run: create venv, install deps, download english weights, start API
python onekey.py server     # Afterwards: start the API directly
python onekey.py gpu        # CUDA torch (Windows/Linux; macOS falls back to CPU/MPS)
python onekey.py stop       # Stop the service
python onekey.py status     # Status + health check
python onekey.py detach     # Start in the background (frees your terminal)
python onekey.py doctor     # Preflight: Python/uv/venv/disk/model/download source
python onekey.py model      # Download weights (--source mirror|official)
python onekey.py panel      # Open the web management panel (gui is an alias)
python onekey.py web        # Open the status page in the default browser
```

> `onekey.py` handles platform differences for you: venv paths (`Scripts\` vs `bin/`), uv lookup (bundled / system / fallback to `python -m venv`), torch install source, process-stop mechanics (Windows `taskkill` vs Unix signals).

### Download sources (China / overseas)

onekey does **not** auto-detect your region; it guides you instead:

- **Mainland China** (default, fast): mirror `hf-mirror.com`
- **Everyone else**: official `huggingface.co` (`--source official` or set `HF_ENDPOINT`)
- **Manual**: download from the mirror / official / [ModelScope](https://www.modelscope.cn/models/convaiinnovations/laya) and drop it into `models/laya/`

Run `python onekey.py doctor` first to preflight the environment and disk space (~840MB model).

### Management panel (Web GUI)

```bash
start-gui.bat          # Windows: opens the panel in your browser
./start-gui.sh         # Linux / macOS
python onekey.py panel # or call it with Python on any platform
```

`start-gui` starts a local management service (`http://127.0.0.1:8398`) and **opens it in your browser automatically**: start/stop the service, check health & model status, download weights, install GPU dependencies, run environment checks, and tail logs live.

> A browser panel because many Python distributions (especially minimal uv-installed ones) ship without tkinter, which makes double-click GUIs silently do nothing; a web panel works on 100% of platforms. `python onekey.py gui` now points to the same web panel.

### Interactive demo (demo.html)

`demo.html` is a hands-on playground: type text + typed questions on the left, hit "decide", and see the classification / score / probability result.

It runs in **pure front-end demo mode**: results are simulated locally in your browser by keyword rules — **no service needed, nothing is called**. Double-click to open (or host it anywhere static) to get a feel for how Laya is called and what it returns. To try the real model, start the local service and call `POST http://127.0.0.1:8399/predict` (see LAYA.md).

---

## HTTP API

| Method | Path | Purpose |
|------|------|------|
| GET | `/health` | Liveness + loaded/available checkpoints |
| GET | `/v1/models` | Model list (`jev-latest` = english) |
| POST | `/predict` | Laya-native: `{"state","questions","model"?}` |
| POST | `/v1/systemone` | TypeSafe-compatible: set `TYPESAFE_BASE_URL=http://127.0.0.1:8399` |
| GET | `/` | Human-readable status page with curl examples |

```bash
curl -s http://127.0.0.1:8399/predict -H "Content-Type: application/json" -d @- <<'EOF'
{"state":"We were billed twice for March. Please refund the duplicate or we will cancel.",
 "questions":{"department":{"type":"choice","instructions":"Which team?","criteria":{"billing":"refunds","technical":"bugs","sales":"pricing","other":"misc"}},
              "urgency":{"type":"score","instructions":"How urgent?","criteria":["none","soon","blocking"]},
              "churn_risk":{"type":"noul","instructions":"Threatens to cancel?"}}}
EOF
```

Agent integration details in [`LAYA.md`](LAYA.md).

## Agent Skill (Claude Code / Cline / Codex …)

Local decisions don't need an MCP server — agents on the same machine just call HTTP directly. The repo ships a standard skill file, [`skills/laya/SKILL.md`](skills/laya/SKILL.md); any Agent-Skills-capable agent loads it and calls the service correctly (health probe → `POST /predict` → interpreting choice / score / noul probabilities).

### Method 1: one prompt — let the model install it (recommended)

You're already using an LLM — put it to work. Paste this into your agent as-is:

```text
Please install the Laya local decision skill for me:
1. Download https://raw.githubusercontent.com/rexleimo/laya-setup/main/skills/laya/SKILL.md
2. Save it as .claude/skills/laya/SKILL.md (create the directory if it doesn't exist; if
   you are not Claude Code, put the content into your own skill/rules mechanism, e.g.
   CLAUDE.md or your system prompt)
3. Read it through, then tell me: in which situations you would use it, and how to call
   each of the three question types (choice / score / noul)
4. Also request http://127.0.0.1:8399/health and tell me whether the Laya service is
   currently running
```

The agent downloads it, installs it, learns it, and checks your service status — you paste once.

### Method 2: manual download

**Claude Code (project-level)** — run in your project root:

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

For all-project availability, install into `~/.claude/skills/laya/` instead. The agent then loads it on demand; you can also just say "read `.claude/skills/laya/SKILL.md`" to activate it immediately.

**Other agents / manual**: open the
[full SKILL.md](https://github.com/rexleimo/laya-setup/blob/main/skills/laya/SKILL.md)
in a browser and paste the whole thing into the agent's system prompt or rules file (`CLAUDE.md` / `.cursorrules` / Cline rules, etc.).

> The download is a single-file, drop-in skill: nothing to register, nothing beyond the file itself; the only prerequisite is a running local Laya service (if it's down: `python onekey.py run`, or click "Start" in the panel).

Full field reference and model variants in [LAYA.md](LAYA.md).

## Model variants

```bash
python onekey.py model                                   # english (default, ~840MB)
python download_model.py --variant multilingual          # multilingual (~650MB)
python download_model.py --variant typed-decisions       # typed-decision head (~840MB)
```

Non-Latin text automatically routes to multilingual (if downloaded), otherwise english.

---

## FAQ

**Q: Do I need a GPU?** No. CPU is enough (~35–400ms per call). For more speed use `onekey.py gpu` (NVIDIA CUDA); macOS uses CPU/MPS.

**Q: How big are the weights, where do they come from?** ~840MB. Mirror `hf-mirror.com` by default, official `huggingface.co` overseas, or download manually from ModelScope into `models/laya/`.

**Q: How is this different from calling a cloud LLM?** Laya doesn't generate text — it returns judgments **with calibrated probabilities** for typed questions, built for triage / routing / guardrail decisions; and it's fully local, so private data never leaves the machine.

**Q: Can it plug into my existing toolchain?** Yes. Set `TYPESAFE_BASE_URL=http://127.0.0.1:8399` as a TypeSafe-compatible drop-in; AI agents learn to call it from the bundled `skills/laya/SKILL.md`.

**Q: How do I stop the service?** `python onekey.py stop`, Ctrl+C in the foreground, or the "Stop" button in the management panel.

---

## About · Mengshou Programming (RexAI)

**This project is maintained by [Mengshou Programming (RexAI · 梦兽编程)](https://rexai.top).** We write about agent engineering on our blog and ship our own open-source projects — if this repo helped you, follow along:

**Blog & products: [rexai.top](https://rexai.top)** · **GitHub: [@rexleimo](https://github.com/rexleimo)** · **All products: [rexai.top/products](https://rexai.top/products/)**

A few representative open-source projects:

| Project | In one line |
|---|---|
| [HNO](https://github.com/rexleimo/agno-Go) | Go-native multi-agent framework with shared Agent / Team / Workflow components and reproducible performance |
| [AIOS](https://github.com/rexleimo/aios) | Local-first agent workflow layer adding memory, teams and verification to codex / claude / opencode |
| [rex-harness](https://github.com/rexleimo/rex-harness) | The workflow kernel beneath AIOS (Observation → Fact → Capability → Command → Evidence) |
| [Hermes Console](https://github.com/rexleimo/hermes-setup) | Visual ops console for the Hermes Agent — install, gateway, models & channels, no SSH needed |
| [Yilan 一览](https://github.com/rexleimo/yilang-browser) | iOS-native-style mobile browser centered on bookmarks; privacy-first, free, no login |
| [REX-GAME](https://game.rexai.top) | A playable folk-culture museum — oracle bones, solar terms and more, right in your browser |

---

## Star history & acknowledgments

If this saved you the pain of setting up a local model environment, a Star is appreciated. Model & inference come from [NandhaKishorM/laya](https://github.com/NandhaKishorM/laya); this repo focuses on **cross-platform one-click launch & operations**.

**Topics:** `laya` `local-ai` `decision-model` `system-1` `one-click` `self-hosted` `typesafe` `agent-skills` `on-premise` `llm-alternative` `python` `cross-platform`
