# 验证记录

日期：2026-10-08。下列记录只描述实际执行的检查，不代表真实模型的题目质量或所有平台兼容性。

## 已执行

- 环境：Linux，Python 3.12.14；Node.js 24.19.0 用于 JavaScript 语法检查。
- 在新建虚拟环境安装固定直接依赖成功；随后另建全新虚拟环境，从 `requirements-lock.txt` 安装锁定的完整依赖成功。
- `python -m pip check`：通过，无依赖冲突。
- `python -m pytest`：112 项通过。包含独立安全回归检查、模型模拟响应和离线业务流程。
- `python -m ruff check .`、`python -m ruff format --check .`：通过。
- `node --check app/static/app.js` 与端到端脚本语法检查：通过。
- `python -m compileall -q app tests`：通过。
- 首页、CSS、JavaScript 与 `/openapi.json` 的本地 TestClient HTTP 请求均为 200；这不等同于浏览器渲染测试。
- 验证过同源限制、并发重复提交、资料/题目导入的原子性、不可恢复的超限导出拒绝、PDF 嵌套压缩内容及解析进程清理。

测试有一条上游 Starlette TestClient 关于 httpx 适配的弃用警告，不影响当前断言。请在后续依赖升级时重新验证，不要简单忽略未来的兼容性变化。

## 尚未验证，不能写作“通过”

- 真实浏览器交互和视觉结果：当前执行环境阻止本地浏览器访问/启动，因此没有得到完整浏览器通过证据。已提供 [`tests/e2e/`](tests/e2e/README.md) 的 Playwright 脚本及本机执行步骤。该脚本本身只完成语法检查，实际运行仍可能需要调整。
- 真实 DeepSeek 或其他模型的网络连通、费用、吞吐、答案准确率、知识覆盖与学习效果：未使用任何真实密钥或付费 API；模型集成测试全部使用模拟响应。
- Windows、macOS 和 Python 3.11 的实际运行：给出安装说明及 CI 配置，但不把配置等同于验证结果。
- 公网、多用户和恶意文件服务场景：本项目不具备生产部署所需的认证、用户隔离、配额和全面运维能力。
- GitHub Actions 线上结果：以发布后对应提交的 Actions 状态为准；本地成功不代表远端检查已运行或已通过。

学生应在自己的环境复核上述未验证项，并在 `docs/templates/` 的空白记录中保存实际命令、输入、日期、输出和失败情况。不要把本文件复制成自己的模型效果实验结果。
