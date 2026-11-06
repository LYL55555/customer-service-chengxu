# 澄序 · 客户顾问微信话术助手

为虚构精品皮具品牌的客户顾问整理聊天和客户记录，生成三条可选择的中文微信。覆盖生日节日问候、推荐、购后关怀、沉睡客户唤回、活动邀请和价格异议。

当前源码 **0.21.1**。单页网页、Python标准库后台、SQLite本地保存；截图使用本机OCR并由顾问复核。有效生成恰好三条，缺必要原文时请顾问处理。不会自动发送微信。

## 操作演示

[观看55秒操作演示](review/DEMO_continuous_v0.21.1.mp4)

实际新建客户、选场景与商品、填入客户消息、生成三条、选择复制并显示成功提示。删去空等、放慢快速滚动，放大阅读区域并添加重点圈线；保留原操作顺序和模型原文。原录制生成1次、复核1次，无重试；本次剪辑不调用模型，不据片长宣称节时。截图导入/复核、原生粘贴及清晰的刷新操作不在本片展示范围。[输入、三条及复核原记录](review/continuous_demo/REAL_RUN.json) · [录制与节奏处理说明](review/DEMO.md)。

## 本地运行

需要Python 3.10以上。macOS支持本机截图OCR；其他平台可用聊天文字和保存结果。

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cp CONFIG_TEMPLATE.txt .env
```

在本地.env填入自己的MODEL_API_KEY，再运行：

```sh
python3 app.py
```

打开 [http://127.0.0.1:8765/](http://127.0.0.1:8765/)。新建客户只填称呼；选择场景、放截图或输入聊天，必要时补一句背景，点击生成即可选一条复制。接口未配置时会明确提示。key只留在本地后台，.env及运行数据已忽略。

无key查看保存回放：`python3 scripts/load_submission_demo.py`，然后在当前客户选择“提交回放 · 虚构顾问小林”下的客户。保存回放与上面的实际新生成录像分别标注；已知编辑问题不因可复制而算完全解决。详细平台和启动说明见[RUN_THIS_FIRST.md](RUN_THIS_FIRST.md)。

## 评审材料

- [业务、方法与实际架构](review/B_METHOD.md)
- [完整50例150条原文](review/C_50_ORIGINALS.md) · [规定八列Excel](review/C_50_ORIGINALS.xlsx)
- [评估及截图](review/D_EVALUATION.md) · [缺陷与版本对照](review/E_DEFECTS.md)
- [完整work log](WORK_LOG.md) · [各轮实际版本](review/VERSIONS.md)
- 解压下载本仓库后，可直接打开`review/index.html`按阅读路径查看附件

原始50例和初始评分保持历史，后续修复、离线重验与模型对照分列，不拼最好结果。Pro仅作两案对照，未接入；正常使用仍为DeepSeek Flash。用户已认可N16普通判断尺度并结束该项。

## 范围与限制

全部业务数据虚构。仓库不含模型key、.env、运行客户数据库、题目原文件或真实客户资料。不是生产CRM，没有云同步、真实库存/订单接口、自动发微信或生产认证。

文案仍可能多问一句、带内部自述，程序和模型复核也可能误判；具体原句见评估。没有真人顾问使用意愿、总节时或优于通用模型文案的验证。真实AI开发对话截图尚缺：[手动补图清单](review/AI_CHAT_GAPS.md)，应用录屏不能替代。
