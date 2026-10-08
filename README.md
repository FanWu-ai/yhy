# 基于大语言模型的智能出题与错题管理系统设计与实现

一个面向本科毕业设计的可运行、可解释的学习系统：导入课程资料，生成带原文引用的单项选择题，在线练习、自动判分、积累错题并查看学习统计。

**无需训练模型。默认离线、无需密钥、不会产生 API 费用。** 真实模式调用配置好的 OpenAI 兼容接口。这个项目由 AI 辅助搭建，是需要学生阅读、验证、修改和说明的工程基础，不是已完成的学术研究，也不提供虚构实验结果、创新结论或代写完成的毕业论文。

## 先跑起来

需要 Python 3.11 或以上（本地实际验证版本为 3.12）。不需要 Node.js 构建前端，不需要数据库服务、GPU 或 Docker。

```bash
git clone https://github.com/FanWu-ai/yhy.git
cd yhy
python -m venv .venv
```

激活虚拟环境：

```bash
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

安装与启动：

```bash
python -m pip install -r requirements-lock.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 **http://127.0.0.1:8000**。`Ctrl+C` 停止服务。如果端口被占用，可将 `8000` 改为 `8001`。

> 当前版本是单人、本机使用的教学系统，无登录和用户隔离。不要使用 `--host 0.0.0.0`、公网转发或直接部署到公开服务器。API key 只在后端环境变量中保存，前端没有密钥输入框。

### 五分钟演示

1. 在首页载入“原创演示资料”，系统会导入 Python 基础材料和 10 道固定题。
2. 在题库选择题目，开始练习；故意答错一题，提交后查看得分、解析及原文引用。
3. 打开错题本，重练后答对，观察“已掌握”状态和统计变化。
4. 查看练习历史；导出题库 JSON，再导入验证去重。
5. 上传自己的 UTF-8 `.txt`、`.md` 或包含文本层的 `.pdf`。

离线题来自本项目原创固定题库，不是大模型生成，也不会为任意资料“假装生成”。离线模式只支持内置 Python 资料和基础难度；其他资料、中等或困难难度需要真实 API。重复演示题会复用，不会无限增加。

## 已实现的功能

| 模块 | 功能 |
|---|---|
| 课程资料 | 粘贴文本，上传 TXT/Markdown/文本 PDF，按课程标记并查看原文 |
| 出题 | 离线演示；真实 OpenAI 兼容 JSON 出题；难度、题数、原文引用 |
| 输出校验 | 四个非空不重复选项、合法答案、题数、难度、引用必须在原文内 |
| 题库与练习 | 选择题目组卷；答题时隐藏答案；后端判分；遗漏算错 |
| 错题本 | 自动收集、累计错误次数、重练、手动或答对后标记掌握 |
| 学习记录 | 历史成绩、累计正确率、知识点正确率、最近练习结果 |
| 数据导入导出 | `quiz-study-v1` JSON 题库备份；全量校验、原子导入、去重 |
| 本地防护 | 同源与自定义请求头校验、CSP、参数化 SQL、大小限制、错误脱敏 |

**边界**：只有单项选择题；没有 OCR、模型训练、向量库、自动考试监考、多用户权限或云同步。知识点标签和难度来自生成内容，不是经过标定的能力测量。引用存在性校验不能证明答案正确、引用相关或教学质量合格。

## 启用真实 API

只有完成以下配置、选择真实 API，并在每次出题时明确确认资料外发，系统才会请求服务商。

```bash
# macOS / Linux
cp .env.example .env
# Windows PowerShell
Copy-Item .env.example .env
```

在本机编辑 `.env`：

```dotenv
API_MODE=openai
LLM_API_KEY=在本机填写自己的密钥
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_TIMEOUT_SECONDS=60
DATABASE_PATH=data/app.db
```

重启后端。`LLM_BASE_URL` 是可信服务商的 HTTPS 基础地址，程序在后面追加 `/chat/completions`；其他兼容服务可以使用它要求的基础路径（例如末尾包含 `/v1`）。服务商须支持聊天补全、`response_format={"type":"json_object"}` 和配置的模型。不要将密钥配置到不信任的地址。

- 每次调用会把**选定资料的完整文本**发给所配置服务商，可能产生费用；系统不上传原始 PDF 文件，但会发送提取出的文本。
- 学生个人信息、保密课程资料或无权外发的内容不要上传到真实模式。
- `.env`、数据库、备份和私有实验目录已加入 `.gitignore`。不要将密钥写入代码、截图、导出文件或 GitHub。
- 模型响应失败、空内容、结构不符、引用错误或截断时，整批不保存，不自动重试；重试需要再次主动点击。
- 本仓库使用模拟响应测试 API 适配器，**没有用真实密钥进行付费连通性或教学效果测试**。

接口依据：[DeepSeek API 官方说明](https://api-docs.deepseek.com/)、[JSON 输出说明](https://api-docs.deepseek.com/guides/json_mode/)。默认模型名按 2026-10-08 官方页面设置；请以自己的账户及服务商最新文档为准。

## 数据与限制

- 上传文件最多 5 MB，PDF 最多 40 页；资料文本为 20–30000 字符。
- PDF 仅解析文本层；加密、扫描、损坏或过于复杂的文件会拒绝，换成 UTF-8 文本即可。
- PDF 在独立进程内处理，12 秒墙钟超时；Linux 另设 512 MB 地址空间和 8 秒 CPU 上限，并限制解码流大小。其他系统没有相同的进程内存硬限制，不适合处理来源不明的恶意文档。
- 一次生成 1–10 题，一次练习最多 50 题；同一时刻只运行一个真实出题请求。
- 数据存在 `data/app.db`。导出功能只包含资料和题目，**不包含成绩、错题状态或 API key**。
- 完整备份：先停止程序，再复制 `data/`。恢复前保留旧备份，再替换数据库；不要在服务运行时覆盖数据库。
- 导入只接受本系统格式、最多 100 份资料和 500 道题，文件最大 5 MB；不执行导入内容或解压文件。导入不覆盖已有资料或学习记录。
- 时间以 UTC 保存，界面按浏览器本地时间显示。没有收集遥测数据或加载第三方 CDN。

## 测试与检查

`requirements-lock.txt` 固定了本次验证的直接与间接依赖；`requirements.txt`/`requirements-dev.txt` 提供更易维护的直接依赖清单。

```bash
python -m pip check
python -m pytest
python -m ruff check .
python -m ruff format --check .
# 仅语法检查需 Node.js；运行本系统不需要 Node.js
node --check app/static/app.js
```

当前已执行的结果及尚未验证的范围见 [验证记录](VERIFICATION.md)；可选浏览器端到端脚本见 [tests/e2e](tests/e2e/README.md)。

测试包含离线全流程、错题重练、重复/并发提交、数据持久化、导入回滚、上传边界、文本 PDF、模型输出异常、引用校验、同源防护及模拟 API。测试会阻止真实 HTTPTransport 请求，避免误用付费 API。GitHub Actions 在独立环境执行上述检查。

浏览器端请按[测试与实验指南](docs/06-testing-and-experiments.md)手动复核演示流程、取消离开、重复点击、窄屏和失败提示；后端测试通过不等于所有浏览器或真实模型效果已经通过。

## 项目结构

```text
app/
  main.py               HTTP 接口、组卷判分、错题统计、数据导入导出
  config.py             后端环境配置
  schemas.py            Pydantic 严格数据模型
  database.py           SQLite 表结构与事务
  generation.py         模型提示、兼容接口、输出与引用校验
  materials.py          文本/PDF 有界解析
  demo.py               原创离线资料和固定题目
  templates/index.html  页面骨架
  static/               原生 JS 与响应式 CSS
examples/               可直接上传的原创演示资料
tests/                  单元、API、离线流程与安全回归测试
docs/                   开题、设计、实验、论文与答辩指南
requirements*.txt       直接依赖与锁定依赖
.env.example            不含密钥的配置示例
```

### 接口与数据库

完整机器可读接口规范在 http://127.0.0.1:8000/openapi.json 。为避免默认交互文档的外部 CDN 与站点 CSP 冲突，未启用 `/docs` 和 `/redoc`。变更接口必须带 `X-Requested-With: quiz-app` 请求头；浏览器请求还必须同源。

主要路由：`/api/materials`、`/api/materials/upload`、`/api/demo/seed`、`/api/generate`、`/api/questions`、`/api/quizzes`、`/api/quizzes/{id}/submit`、`/api/wrongbook`、`/api/history`、`/api/stats`、`/api/export`、`/api/import`。查看[系统设计](docs/04-architecture-and-api.md)了解实体关系和数据流。

六张表分别保存资料、题目、练习会话、答题记录、错题状态、生成请求状态。所有 SQL 参数化；提交练习使用 SQLite 写事务，重复提交返回第一次结果。程序不接收前端分数或正确答案作为评分依据。此设计适合单机学习，不是防作弊考试系统。

## 毕业设计怎么做

从 [docs/README.md](docs/README.md) 按顺序阅读。建议先跑通与讲懂现有系统，再做自己的课程样本、人工题目质量评审、失败分析与小范围改进。学校要求、导师确认、合规数据授权、真实实验和最终论文本人负责。

可如实讨论的工程内容：课程材料到结构化题目的工作流、严格校验与拒绝策略、可追溯引用、错题闭环、可复现实验。不要把“调用 API”写成“自主训练大模型”，不要把固定演示题写成模型效果，不要把自动化测试数量当作学习成效证据。
