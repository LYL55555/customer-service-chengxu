# 原50例 · 0.13.6固定版本复测

本轮只修共同前置判断，六案均不再被本地错误要求补资料。50案输入逐值/字节不变，不给编号设生产例外。

实际完成50/50案；49组保留恰好三条原始字符串；程序交付34组，其余按原失败记录。

请求94次，已报告2,167,942 token；无usage 1次（未知不当0）。每案每阶段本轮只一次、无自动重试。

[阅读全部原文](OUTPUTS.html) · [八列CSV](OUTPUTS_8_COLUMNS.csv) · [完整JSON](OUTPUTS.json) · [冻结源码](source_at_freeze.zip) · [调用账本](rerun.json)

这是已见开发案例的新版本复测，不是新的未见集。原50首轮数据/评分、旧失败和独立报告不改。前置允许开始不等于话术质量通过；模型复核、程序交付、开发者阅读与用户自己愿不愿发分别判断。未交付原文展示仅供诊断，不能当有效回复。

## 未交付案

| 案例 | 状态 | 原错误 |
|---|---|---|
| F12 | error | {'code': 'invalid_output', 'message': '接口未满足本次约定字段（$ fields），不属于可明确兼容的空内部字段；原响应已保留，整组未采用。', 'retryable': False} |
| F13 | error | {'code': 'policy_check', 'message': '该商品断言没有明确对应商品，请先核对当前对象；未按旧勾选猜测。', 'retryable': True} |
| F18 | error | {'code': 'policy_check', 'message': '轻行肩包的dimensions_cm依据为：22 × 16 × 7 cm；该断言没有同一商品资料支持，未知不能解释成没有。', 'retryable': True} |
| F20 | error | {'code': 'invalid_review', 'message': '复核结论的完整候选或事实依据未通过检查；原始复核保留，不能当作已证实的问题。', 'retryable': False} |
| F25 | error | {'code': 'policy_check', 'message': '没有实际执行记录支持这项已查询或已完成动作；未来协助不等于已执行。', 'retryable': True} |
| F28 | error | {'code': 'invalid_review', 'message': '复核结论的完整候选或事实依据未通过检查；原始复核保留，不能当作已证实的问题。', 'retryable': False} |
| F29 | error | {'code': 'quality_review', 'message': '候选未通过上下文与商品政策复核；请查看记录中的具体问题后修改输入或重试。', 'retryable': True} |
| F30 | error | {'code': 'invalid_review', 'message': '复核结论的完整候选或事实依据未通过检查；原始复核保留，不能当作已证实的问题。', 'retryable': False} |
| F31 | error | {'code': 'quality_review', 'message': '候选未通过上下文与商品政策复核；请查看记录中的具体问题后修改输入或重试。', 'retryable': True} |
| F32 | error | {'code': 'quality_review', 'message': '候选未通过上下文与商品政策复核；请查看记录中的具体问题后修改输入或重试。', 'retryable': True} |
| F33 | error | {'code': 'quality_review', 'message': '候选未通过上下文与商品政策复核；请查看记录中的具体问题后修改输入或重试。', 'retryable': True} |
| F35 | error | {'code': 'invalid_review', 'message': '复核结论的完整候选或事实依据未通过检查；原始复核保留，不能当作已证实的问题。', 'retryable': False} |
| F37 | error | {'code': 'invalid_review', 'message': '复核结论的完整候选或事实依据未通过检查；原始复核保留，不能当作已证实的问题。', 'retryable': False} |
| F43 | error | {'code': 'invalid_review', 'message': '复核结论的完整候选或事实依据未通过检查；原始复核保留，不能当作已证实的问题。', 'retryable': False} |
| F47 | error | {'code': 'policy_check', 'message': '没有定价原因资料，尺寸、材质名称或重量差异不能证明差价的原因；可比较已知参数，不要替品牌编定价解释。', 'retryable': True} |
| F50 | error | {'code': 'provider_error', 'message': '模型接口返回 HTTP 402，请核对地址、模型名及接口参数。', 'retryable': False} |

## 这轮的关键区分

- 六案前置已修，原输入没有增加任何一字；F26/F34最终交付，F29/F31/F33在质量复核被拦，F35因复核依据校验失败，均不是再次要求顾问补背景。
- F12有三段可读原字符串但合同坏掉，未修成成功；其第2条还把包体尺寸说成包内尺寸。F50没有候选：原响应HTTP402 / Insufficient Balance，余额不足；已停止云调用。恢复余额后须另存F50补充验证，不能回填本轮失败。
- 开发者阅读全文后另外标出F11的适配推断、F15不反光、F21渠道范围、F23未知清洁剂试擦、F27先断言不需维修、F46含税、F47定价因果等；有些被原复核pass漏过。原文及判断理由在DEVELOPER_NOTES.json，非新的独立signoff。
- 复核也有错误/过强理由，例如F20把申请混成批准、F32买过不能说选过、F35/F37把未来协助当完成；程序还有物品尺寸和来源域误拦。不同问题分别记录，不靠复核pass宣布质量通过。
- 原0.12.0首轮和评分不覆盖。这是已见案例的0.13.6新版本复测，不计算跨轮最佳通过率。这里只完成已授权的共同前置修复，没有顺便修改生成/复核/事实检查。

[DeepSeek官方402错误码说明](https://api-docs.deepseek.com/quick_start/error_codes/)：本轮F50原响应也明确给出余额不足，非顾问需要补资料。

