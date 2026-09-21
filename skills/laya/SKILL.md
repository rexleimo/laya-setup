---
name: laya
description: 调用用户本机的 Laya 决策服务（http://127.0.0.1:8399）。当需要对文本做判断而非生成时使用：分类/路由（choice）、程度评分（score）、是/否判断（noul），如工单分诊、邮件优先级、提示词护栏、流失风险、情感极性。单次前向返回带校准概率的答案，CPU 毫秒级。Laya 不生成文本。
---

# Laya — 本地决策服务调用指南

Laya 是跑在用户本机的 System-1 决策模型：**只做判断，不生成文本**。一次请求可以同时
问多个类型化问题，单次前向全部回答（CPU 约 200–400ms；服务启动后首次加载模型约 30s）。

## 0. 先探活

```bash
curl -s --max-time 3 http://127.0.0.1:8399/health
```

返回 `{"status":"ok",...}` 才继续。不通就**不要硬调**：告诉用户「Laya 服务没在运行，
请先启动（`python onekey.py run`，或打开管理面板点「启动服务」）」，等启动后再试。

## 1. 调用：POST /predict

```bash
curl -s http://127.0.0.1:8399/predict -H "Content-Type: application/json" -d @- <<'EOF'
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
EOF
```

要点：

- `state`：待判定内容。字符串，或对象（如 `{"from":…, "subject":…, "body":…}`）
- `questions`：非空对象；把要问的问题**一次全放进来**，服务单次前向同时回答
- `model` 可省略；非拉丁文本会自动路由到 multilingual（若已下载），否则用 english

## 2. 三种题型（必须严格遵守）

| type | 用途 | criteria 写法 | 答案字段 |
|------|------|---------------|----------|
| `choice` | 分类 / 路由 / 意图 | **对象** `{选项名: 一句话描述}` | `choice` + `probabilities` + `confidence` |
| `score` | 程度评分（紧急度/情绪等） | **数组** `[低 → 高]`，每档一句描述 | `score`（浮点，档位期望位置）+ `probabilities` |
| `noul` | 是 / 否判断 | 不需要 criteria | `noul`（0–1 概率） |

## 3. 结果怎么用

- `choice`：直接取 `choice`，向用户转述时带 `confidence`（例：「判断为账单问题，置信度 96%」）
- `score`：浮点是各档的期望位置（如 1.86 = 3 档制里偏向第 2 档），对照 criteria 数组解释
- `noul`：0–1 概率，按任务定阈值（如 >0.5 视为「是」），转述时说概率不说黑话
- 概率低并非无效信号：多分类下 40% 也可能是显著领先的类别，**看相对差距**而不是绝对值
- **不要**让 Laya 写文案、总结、翻译——它只返回判断，没有生成能力

## 4. TypeSafe 兼容端点（可选）

已有 TypeSafe SDK 工具链时可零改代码切换：

- 端点 `POST /v1/systemone`，请求/响应形状与 `docs.typesafe.ai/api` 一致
- 环境变量 `TYPESAFE_BASE_URL=http://127.0.0.1:8399`，`model` 传 `jev-latest`

## 5. 更多

模型别名（`jev` / `en` 等）、multilingual / typed-decisions 变体下载、字段细节，
见本仓库 `LAYA.md`；交互式体验见仓库 `demo.html`（纯前端模拟，无需服务）。
