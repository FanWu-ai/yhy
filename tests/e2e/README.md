# 可选的浏览器端到端冒烟测试

本目录是独立的前端验证工具，不参与应用安装或启动。主程序无需 Node.js 或前端构建。

## 当前验证状态

脚本已通过 `node --check` 语法检查，但尚未在本次交付环境完整执行。该环境的浏览器/本地连接策略阻止了运行。不要将此脚本的存在视为界面已通过浏览器验证。后端测试结果应以项目测试报告为准。

真实大模型请求也不在本脚本验证范围中。API 外发确认测试使用虚拟配置和请求拦截，仅验证点击“取消”后不会调用生成接口，不会发送资料到外部服务或产生 API 费用。

## 安装

需要 Node.js 20 或更新版本。进入本目录执行：

```bash
npm ci
npx playwright install chromium
```

如系统缺少 Chromium 运行所需依赖，请按 Playwright 官方安装提示处理。不要为测试关闭浏览器安全检查。

## 在独立测试数据库上启动服务

测试会添加示例资料、HTML 安全测试资料和题目，并提交多次练习。请勿连接自己的实际学习数据库或公开部署。启动服务前，请确保 `API_MODE=demo`。

从项目根目录，在一个终端运行（Unix shell 示例）：

```bash
API_MODE=demo DATABASE_PATH=data/e2e-smoke.db python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Windows PowerShell：

```powershell
$env:API_MODE = "demo"
$env:DATABASE_PATH = "data/e2e-smoke.db"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

建议每次使用一个新的测试数据库文件，以保持结果可比较。默认只访问本机 `127.0.0.1:8000`。

在另一终端进入本目录执行：

```bash
npm test
```

可选环境变量：

- `TEST_BASE_URL`：已启动的本地服务地址，默认 `http://127.0.0.1:8000`。
- `CHROMIUM_PATH`：现有 Chromium 可执行文件绝对路径；不设置时使用 Playwright 安装的浏览器。
- `TEST_OUTPUT_DIR`：截图保存目录；默认系统临时目录下的 `zhiti-browser-smoke`。

例如：

```bash
TEST_BASE_URL=http://127.0.0.1:8001 npm test
```

## 覆盖范围

1. 初始加载与 JavaScript 运行错误收集。
2. 示例资料初始化、基础难度固定出题。
3. 未答题校验、练习离开时取消/确认。
4. 题库选题、作答提交、得分与自动收录错题。
5. 标记掌握/待复习与错题专项重练。
6. 历史详情与题库 JSON 导出。
7. 粘贴资料中的 HTML 标签只按纯文本展示。
8. 导入题目、选项、解析及引文中的 HTML 不执行。
9. 取消真实 API 外发确认后，生成请求数为零（模拟配置）。
10. 1440px 桌面与 390px 手机布局，检查页面无横向溢出。

通过时打印每项 `PASS` 及 JSON 汇总，并输出桌面、结果页与手机截图。失败时以非零状态退出，需修复或记录阻塞，不应写成已通过。
