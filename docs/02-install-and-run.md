# 从零安装与运行

本文先运行无需密钥的演示模式。全部命令在项目根目录执行，也就是能看到 `requirements.txt`、`requirements-dev.txt` 和 `app/` 的目录。不要把终端里的提示符、解释文字和命令一起复制。

本项目使用 Python 3.11 或更新的兼容版本。为减少新手环境差异，以下示例固定以 Python 3.11 建立环境。最终测试所用版本见仓库验证记录。Windows 命令是适配说明，不能据此声称已在你的 Windows 电脑上验证。

## 1 准备软件

1. 从 [Python 官方下载页](https://www.python.org/downloads/) 获取适合自己系统的 Python。安装时确认包含 pip；Windows 使用官方启动器时可以执行 `py`。
2. 准备一个现代浏览器，如 Edge、Chrome 或 Firefox。
3. 准备编辑器。可以使用 VS Code，也可以用自己熟悉的编辑器。
4. Git 不是第一次运行的必需品，GitHub 下载 ZIP 也能运行；后续记录开发过程推荐学习 Git。
5. Node.js 仅用于检查本仓库 JavaScript 语法等开发检查，运行本项目网页不需要启动 Node 服务，也没有 npm 构建步骤。若执行完整本地检查，按仓库检查说明安装官方 Node.js。

不要从来历不明的网站下载所谓“项目专用安装器”。不要为解决错误关闭系统安全软件或把整个电脑的脚本策略改成无限制。

## 2 获取项目

使用 Git：

```text
git clone https://github.com/FanWu-ai/yhy.git
cd yhy
```

如果不用 Git，在项目 GitHub 页面选择 Code → Download ZIP，解压到方便找到的位置，例如 `D:\graduation\yhy`。不要在 ZIP 内直接运行；不要把项目放在只读目录。打开 Windows 文件资源管理器，进入项目根目录，在地址栏输入 `powershell` 后按回车，即可在该目录打开 PowerShell。

在终端执行以下命令，确认当前位置和文件：

```powershell
Get-Location
Get-ChildItem
```

如果看不到 `requirements-dev.txt`，说明进入了错误目录或又套了一层解压目录。先改正目录，再执行安装。

## 3 Windows PowerShell 完整步骤

### 3.1 检查 Python

```powershell
py -3.11 --version
```

应看到 `Python 3.11.x`。如果没有 `py`，但已经安装兼容版本且 `python --version` 正确，可以在下面创建虚拟环境时把 `py -3.11` 替换成 `python`。不要为了本项目卸载其他课程依赖的 Python。

### 3.2 创建隔离环境

```powershell
py -3.11 -m venv .venv
```

创建后会出现 `.venv` 文件夹。虚拟环境把该项目依赖与其他 Python 项目隔离。这里使用环境中解释器的完整路径，因此无需执行 `Activate.ps1`，也无需修改 PowerShell 执行策略。Python 官方文档明确支持不激活环境、直接调用环境内解释器。[Python venv 文档](https://docs.python.org/3/library/venv.html)

### 3.3 安装依赖

只运行系统：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

推荐用于毕业设计复现和测试：安装本次验证锁定的全部依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

两者不必重复执行。`requirements-lock.txt` 固定了本次验证的直接与间接依赖，包含运行和开发检查；`requirements-dev.txt` 是方便维护的开发直接依赖清单。安装期间需要访问 Python 包源。出现网络超时，先检查网络与学校网络规定，不要关闭证书校验。安装结束应没有 `ERROR`；不要仅凭最后一行有下载信息就认为成功。

### 3.4 以演示模式启动

```powershell
$env:API_MODE = "demo"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

终端出现服务启动信息后，在浏览器手动打开：

```text
http://127.0.0.1:8000
```

保持这个终端打开。关闭终端会结束后端服务。停止时回到终端按 `Ctrl+C`，等待进程退出。`127.0.0.1` 表示本机，不需要路由器映射或公网服务器。

### 3.5 验证确实运行

1. 打开主页，确认能看到页面和演示模式提示。
2. 打开 `http://127.0.0.1:8000/openapi.json`，应看到接口规范 JSON。为避免文档页面依赖外部脚本并保持安全策略，本项目关闭 `/docs` 和 `/redoc`，不会提供默认 Swagger 页面。
3. 按 [操作手册](03-use-and-demo.md) 导入演示资料并做一次练习。
4. 停止并重新启动，再看资料和历史是否仍在。默认数据库为 `data/app.db`。
5. 若页面能打开但按钮报错，查看服务端终端的错误，并记录发生前操作。仅打开页面不能证明业务流程正常。

## 4 Linux 安装与启动

先确认系统有 Python 3.11 或更高兼容版本，以及对应的 venv 支持。包管理命令依发行版变化，若创建环境提示缺少 venv，按本发行版官方文档安装对应包，不使用未经检查的远程脚本。

```bash
python3 --version
cd /your/path/yhy
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
API_MODE=demo .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`/your/path/yhy` 是说明用占位路径，必须改成自己的真实目录。命令前缀 `API_MODE=demo` 仅对这次启动生效。浏览器仍访问 `http://127.0.0.1:8000`。如果在无桌面服务器上运行，先完成终端测试；不要为了远程访问直接向互联网开放本项目。

## 5 以后每天怎样打开

安装只需成功做一次，之后通常只需：

1. 打开项目根目录的终端。
2. 执行本系统对应的启动命令。
3. 浏览器访问本机地址。

更新代码后如果依赖文件改变，需要重新安装。把整个文件夹复制到另一台电脑时，重新建立 `.venv`，不要搬运旧虚拟环境。虚拟环境记录的路径可能不再有效。[Python venv 文档](https://docs.python.org/3/library/venv.html)

## 6 开发检查命令

Windows：

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
node --check app/static/app.js
```

Linux：

```bash
.venv/bin/python -m pip check
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
node --check app/static/app.js
```

逐条观察退出结果。`pytest` 收集或运行失败、Ruff 报错、Node 不存在，都不能记为“全量检查通过”。若只需要了解系统运行，可先完成演示；若要交付开发成果，应按本地检查要求补齐。

检查目标和结果记录方法见 [测试与实验](06-testing-and-experiments.md)。不允许把仓库作者的测试结果直接作为自己环境的测试记录。

## 7 可选真实 API 配置

**先确认再配置。** 真实模式会把所选学习资料的完整文本发送给配置的模型服务，且可能计费。只使用自己有权处理、并允许发送至该服务的内容。不要输入真实学生档案、成绩、身份证、账号密码、未公开试题或保密课件。服务商的数据规则不能从“兼容 OpenAI”推断，必须查该服务商的官方说明。

本仓库只提供调用适配；不会替你购买账户、充值或创建密钥。密钥应通过终端环境变量或仓库明确支持的本地配置方式提供。密钥不要写进 HTML、JavaScript、论文截图或 Git 提交。

以下命令只示范变量名字。`YOUR_*` 均须由你自行替换，不能原样运行后声称接通。正式设置密钥时推荐使用服务商或开发环境支持的安全注入方式，注意普通终端命令历史可能保存你输入的内容。不要把包含真实密钥的终端截图分享出去。

Windows PowerShell：

```powershell
$env:API_MODE = "openai"
$env:LLM_API_KEY = "YOUR_PRIVATE_KEY"
$env:LLM_BASE_URL = "https://YOUR_VERIFIED_PROVIDER_BASE_URL/v1"
$env:LLM_MODEL = "YOUR_PROVIDER_MODEL_ID"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Linux：

```bash
export API_MODE=openai
export LLM_API_KEY='YOUR_PRIVATE_KEY'
export LLM_BASE_URL='https://YOUR_VERIFIED_PROVIDER_BASE_URL/v1'
export LLM_MODEL='YOUR_PROVIDER_MODEL_ID'
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

模型标识和地址必须来自同一家已核实服务商的官方文档；不要随意组合一个地址和另一家的密钥。兼容接口不代表所有参数、模型和响应细节都兼容。项目使用的接口形式见 [架构与 API](04-architecture-and-api.md)。

重启后先看页面模式与配置状态，再用公开原创资料请求少量题目，并勾选或提交界面要求的资料外发确认。未确认时应拒绝发起远程生成。一次成功之后，保存去密钥的配置、耗时、模型名和输出进行审核。错误不要靠无上限重试解决。

回到演示模式时，停止服务并重新设置 `API_MODE=demo` 再启动。运行中的 Python 进程一般不会自动读取你之后更改的终端变量。

## 8 数据保存、备份与恢复

默认数据目录为 `data/`，默认 SQLite 文件为 `data/app.db`；可用 `DATABASE_PATH` 配置其他位置。不要把这个目录当作缓存随意清理。

页面“导出备份”导出的是题库备份，只含资料与题目，不含错题状态、练习历史或生成记录。导出内容包含资料正文与答案，仍需按私有数据保存。需要保留全部学习状态时使用下面的停机数据库备份。重要实验开始前另做备份。

需要文件级备份时，先按 `Ctrl+C` 停止服务，确认没有进程写数据库，再复制整个 `data/` 目录到带日期的私有备份位置。不要在不了解 SQLite 工作模式的情况下只复制正在写入的一个文件。

恢复测试在新的测试目录或独立 `DATABASE_PATH` 中进行。题库 JSON 导入只核对资料与题目；停机数据库恢复再核对练习历史和错题状态。不要先删除唯一的旧数据库。版本变化可能改变备份格式，导入前阅读版本说明。

## 9 常见问题

| 现象 | 常见原因 | 排查顺序 |
| --- | --- | --- |
| `py` 或 `python` 找不到 | Python 未安装或启动器不可用 | 重开终端，核对官方安装，确认解释器路径 |
| 找不到 requirements 文件 | 当前目录错误 | 查看目录，进入含 app 和依赖文件的根目录 |
| `No module named uvicorn` | 依赖装到别的 Python | 用本文 `.venv` 解释器安装和启动，不混用全局 pip |
| 8000 端口已占用 | 旧服务仍在运行 | 停止旧进程，或把启动端口改为 8001 并访问对应地址 |
| 浏览器拒绝连接 | 后端没启动或已退出 | 看终端是否仍运行，检查地址、端口与错误 |
| 页面有旧内容 | 浏览器缓存或旧进程 | 确认唯一服务，普通刷新，必要时强制刷新 |
| PDF 没有文字 | 是扫描件、加密文件或布局提取失败 | 换可复制文字的 PDF，或自行整理成 UTF-8 文本 |
| TXT 中文乱码 | 文件不是支持的文本编码 | 用编辑器另存 UTF-8，重新导入并核对内容 |
| 模型 401/403 | 密钥、账户或权限不匹配 | 在服务商官方控制台核对，不把密钥贴进 issue |
| 模型 429 | 配额不足或限流 | 查官方控制台与账单，稍后手动重试，不连续刷请求 |
| 模型返回结构错误 | 兼容性或输出不符合约束 | 保存脱敏错误类别，换小资料或兼容模型，检查适配代码 |
| 数据库只读或锁定 | 权限不足、多个写入者 | 停止重复服务，检查路径，不先删除数据库 |

求助时提供：操作系统、Python 版本、执行命令、去掉密钥与私有路径后的错误、复现步骤、代码版本。不要发送 `.env`、数据库或完整个人资料。
