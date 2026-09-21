# Laya 本地决策服务 — Agent 接入说明

> 把本文件全文粘贴给任何 Agent / 大模型，它就能正确调用本服务。
> 服务地址：`http://127.0.0.1:8399`（本机服务，无需鉴权）
>
> 更推荐：给支持 Agent Skills 的智能体（Claude Code / Cline / Codex …）加载
> 精简技能版 [`skills/laya/SKILL.md`](skills/laya/SKILL.md)，一个文件即学会调用。

## 1. 这是什么

Laya 是一个本地 System-1 决策模型：**不生成文本**，只回答类型化问题，
返回带校准概率的答案。单次前向同时回答所有问题（CPU 约 200–400ms，
首次加载模型约 30s，服务现已预热）。

## 2. HTTP 调用（二选一）

### 方式 A：原生接口 `POST /predict`

```json
{
  "state": "We were billed twice for March. Please refund the duplicate today or we will cancel.",
  "questions": {
    "department": {
      "type": "choice",
      "instructions": "Which team should handle this request?",
      "criteria": {
        "billing": "invoices, payments, refunds",
        "technical": "bugs, outages, system errors",
        "sales": "pricing, new contracts",
        "other": "everything else"
      }
    },
    "urgency": {
      "type": "score",
      "instructions": "How urgent is this request?",
      "criteria": ["no time pressure", "needs attention soon", "blocking issue or hard deadline"]
    },
    "churn_risk": {
      "type": "noul",
      "instructions": "Does the user threaten to cancel or leave?"
    }
  }
}
```

curl 示例：

```bash
curl -s http://127.0.0.1:8399/predict -H "Content-Type: application/json" -d @- <<'EOF'
{"state": "…待判定内容…",
 "questions": {"refund_requested": {"type": "noul", "instructions": "Does the user request a refund?"}}}
EOF
```

### 方式 B：TypeSafe 兼容接口 `POST /v1/systemone`

请求/响应形状与 `docs.typesafe.ai/api` 一致。已有 TypeSafe SDK 工具链时，
只需设置环境变量即可零改代码切换到本地服务：

```bash
TYPESAFE_BASE_URL=http://127.0.0.1:8399
```

`model` 传 `jev-latest` 即可（服务端自动映射到本地 english checkpoint）。

### 辅助接口

- `GET /health` → `{"status":"ok","available":[…],"loaded":[…]}`，调用前可用它确认服务存活
- `GET /v1/models` → 模型列表（`jev-latest` = english）
- `GET /` → 带示例的人类可读状态页

## 3. 问题类型（三种，必须严格遵守）

| type | 用途 | criteria 写法 | 答案字段 |
|------|------|---------------|----------|
| `choice` | 分类（部门/意图/类别） | 对象 `{选项名: 描述}` | `choice` + `probabilities` + `confidence` |
| `noul` | 是/否判断（是否紧急/是否退款/是否流失风险） | 不需要 criteria | `noul`（0–1 概率） |
| `score` | 程度评分 | 数组 `[低…高]`，每项是该档描述 | `score`（浮点）+ `probabilities` |

规则：
- `questions` 是非空对象，`{问题id: {type, instructions, criteria?}}`
- `state` 必填，可以是字符串，也可以是对象（如 `{"from":…, "subject":…, "body":…}`）
- 不要让 Laya 写文案、总结、翻译——它只做判断，不生成文本

## 4. 行为备注

- `model` 参数可省略：非拉丁文本自动路由到 multilingual（若已下载），否则用 english
- 可用 checkpoint：`english`（已加载）、`multilingual`、`typed-decisions`（后两者需先下载）
- 别名：`jev` / `jev-latest` / `laya` / `en` 均指向 english
- 服务为本机手动启动；若 `/health` 不通，在本机项目目录执行 `python onekey.py server`（或双击 `start.bat`）即可恢复
