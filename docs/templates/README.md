# 过程与实验记录模板

这些文件是空白模板，不是已经执行的结果。复制到自己的私有工作目录后填写；个人身份、原始资料和模型响应不应默认提交公开仓库。

| 文件 | 用途 |
| --- | --- |
| proposal.md | 开题报告内容提纲，之后填入学校正式表格 |
| weekly-log.md | 每周开发记录和证据链接 |
| experiment-protocol.md | 实验开始前固定方案、指标和预算 |
| request-records.csv | 每次真实生成请求一行，失败也记录 |
| human-ratings.csv | 每道题每位评分者一行，不覆盖原始分歧 |
| test-records.csv | 每个实际执行用例的预期、实际和证据 |
| requirements-traceability.csv | 需求、实现、测试和论文相互核对 |
| delivery-checklist.md | 最终交付检查 |

CSV 只有表头。可用支持 UTF-8 的表格软件打开并另存，注意不要让软件把 ID 改成科学计数。时间统一写含时区的 ISO 格式；费用必须注明币种和计价来源；不知的数据留空并备注未知。

`human-ratings.csv` 中六个质量维度取 0/1/2，规则见 [实验方案](../06-testing-and-experiments.md)。`usable` 等二元字段使用 0/1；空值表示未评，不能当作 0。评分者用 R01 等匿名标识。模型和失败记录都不要包含 API Key。

`request-records.csv` 记录的是实际请求而非点击次数。`requested_count` 是目标题数，`accepted_count` 为通过校验保存的题数，`reviewed_count` 和 `usable_count` 在人工评估后填写。原始响应路径应指向私有实验材料，公开版本移除不应披露的位置和内容。
