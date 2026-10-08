# 官方技术资料与文献入口

以下链接在 2026-10-08 编写文档时查阅。它们用于核实技术接口和概念，不是“已完成全部文献综述”的清单。官方网站内容、模型名称、价格和政策可能变化，提交论文前再次打开并记录自己的实际访问日期。

论文引用格式以学校模板为准。在线技术文档与研究论文分开使用，不把文档当作本系统效果的独立实验依据。

## 1 工程技术资料

| 来源 | 官方链接 | 在本项目中用于核实什么 |
| --- | --- | --- |
| Python 官方下载 | [Python Downloads](https://www.python.org/downloads/) | 获取受支持的解释器与发行说明 |
| Python venv | [venv](https://docs.python.org/3/library/venv.html) | 创建隔离环境、直接使用环境解释器、重新建立环境 |
| Python sqlite3 | [sqlite3](https://docs.python.org/3/library/sqlite3.html) | Python 的 SQLite 接口、连接、事务等 |
| SQLite | [Foreign Key Support](https://www.sqlite.org/foreignkeys.html) | 外键约束的启用与行为 |
| FastAPI | [Tutorial](https://fastapi.tiangolo.com/tutorial/) | Web API、请求处理与自动文档 |
| Uvicorn | [Settings](https://www.uvicorn.org/settings/) | 启动入口、绑定地址和端口 |
| Pydantic | [Models](https://docs.pydantic.dev/latest/concepts/models/) | 数据模型与输入验证 |
| pypdf | [Extract Text from a PDF](https://pypdf.readthedocs.io/en/stable/user/extract-text.html) | PDF 提取边界，以及扫描件与 OCR 的区别 |
| Jinja | [Template Designer Documentation](https://jinja.palletsprojects.com/en/stable/templates/) | 模板与 HTML 转义 |
| pytest | [Get Started](https://docs.pytest.org/en/stable/getting-started.html) | 测试发现、断言和测试运行 |
| Ruff | [Ruff documentation](https://docs.astral.sh/ruff/) | Python 静态检查与格式化 |

依赖具体版本以仓库依赖文件和实际安装结果为准。上述文档往往默认显示最新版，不要仅因文档更新就声称项目已经升级或完成兼容测试。

## 2 模型接口与数据处理说明

1. OpenAI. [Chat API reference](https://developers.openai.com/api/reference/resources/chat). 用于理解 Chat Completions 请求与响应格式。本项目使用兼容形式，不表示由 OpenAI 托管或已通过 OpenAI 连通测试。
2. OpenAI. [Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs). 用于理解 JSON 输出和更强结构约束的区别。本项目使用 JSON 对象输出请求及本地 Pydantic 校验；不宣称所有服务商都提供同样的严格 JSON Schema 保证。
3. OpenAI. [Data controls in the OpenAI platform](https://developers.openai.com/api/docs/guides/your-data). 仅用于核对 OpenAI 自身的数据控制说明，不能套用到其他兼容服务商。
4. DeepSeek. [Your First API Call](https://api-docs.deepseek.com/). 编写时官方页面列出 OpenAI 兼容地址 `https://api.deepseek.com` 和 `deepseek-flash` 等模型名。项目默认示例取自该页；账户可用性、实际费用与请求是否成功仍须独立核实。

本项目交付验证不使用真实收费密钥，未据此产生真实 API 的准确率或费用结果。接入前应去实际服务商官方控制台核对账户、模型、地址、价目和资料处理规则。

## 3 可核实的基础论文

### 3.1 Transformer 背景

VASWANI A, SHAZEER N, PARMAR N, et al. Attention Is All You Need. 2017. [arXiv:1706.03762](https://arxiv.org/abs/1706.03762).

适用：介绍 Transformer 的基础研究背景。不要把论文中的机器翻译实验结果改写成本项目的出题效果。

### 3.2 检索增强生成背景

LEWIS P, PEREZ E, PIKTUS A, et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. 2020. [arXiv:2005.11401](https://arxiv.org/abs/2005.11401).

适用：讨论语言模型结合外部资料的研究背景，以及与本项目实现的区别。该论文有具体检索与模型训练设置；本项目没有自动获得这些机制。若本版只传入选定资料，应明确写为资料约束生成。

### 3.3 自动问题生成背景

DU X, SHAO J, CARDIE C. Learning to Ask: Neural Question Generation for Reading Comprehension. Proceedings of the 55th Annual Meeting of the Association for Computational Linguistics, 2017: 1342–1352. DOI: 10.18653/v1/P17-1123. [ACL Anthology 原文入口](https://aclanthology.org/P17-1123/).

适用：了解面向阅读理解的自动问题生成任务及其评价。这项研究与本项目的四选一题目、来源校验和错题流程有区别；不直接作为本项目效果结论。

## 4 怎样补充本课题真正需要的文献

导师通常会希望看到与自动出题、题目质量和教学场景更直接相关的研究。建议按下面流程补齐，而不是只引用框架文档。

1. 用中英文关键词检索，例如 automatic question generation、multiple-choice question generation、grounded question generation、educational question quality evaluation，以及“自动出题”“干扰项生成”“题目质量评价”。
2. 优先读取论文原文、作者公开版本、期刊或会议官网。核对作者、题名、年份、发表渠道和 DOI 或稳定链接。
3. 记录研究任务、数据来源、样本数量、评价指标、基线和限制。
4. 找出与本项目相同和不同之处，尤其区分阅读理解问答、多项选择题和错题管理。
5. 只引用真正读过且能支持正文论点的文献；文中编号与参考文献逐一对应。

## 5 阅读记录模板

每篇资料记录六项即可：完整题名与来源、阅读日期、解决的问题、方法与数据、结果和限制、能支持本论文哪一段。不要只摘抄摘要；注明自己尚未验证或没有读到的内容。

本页不提供编造的中文期刊条目、未核实的引用次数或虚构参考文献。学校如要求特定数量、近年文献占比或中文文献，请依据本校要求继续真实检索。
