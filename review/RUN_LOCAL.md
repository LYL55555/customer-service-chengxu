# 本地运行 · 0.21.1

评审材料解压后直接打开外层index.html，无需账户或服务。源码使用本层SOURCE_v0.21.1.zip；历史附录里的旧源码与旧说明仅用于追溯。

解压源码，进入CHENGXU_Source_v0.21.1。Python 3.10以上；本机OCR推荐macOS并安装Swift命令行工具。

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 app.py
```

Windows激活环境使用`.venv\Scripts\activate`。打开http://127.0.0.1:8765/；未配置模型时有明确提示。新客户只填称呼，选六场景，放截图或输入聊天，必要时补一句线下背景，点击生成。截图需先复核导入；已有信息不重复填。没有聊天的生日任务、简单报价无预算都可以开始。

真实生成：在源码根目录手动新建.env，照CONFIG_TEMPLATE.txt填写地址、模型与自己的key。默认DeepSeek Flash，复核同为Flash；模型key只在本地后台。刷新配置或重启服务。初始“已配置，尚未验证连接”指当前进程尚未发请求，不自动花调用探测。模型返回不合规/网络失败明确保留失败，不自动重试。

可选的保存结果回放，不需要key：

```sh
python3 scripts/load_submission_demo.py
```

然后在页面当前客户选择“提交回放 · 虚构顾问小林”下的客户。六个虚构会话包含负重、活动、清洁剂、库存及J01/J02两案；不是新跑六案例。原文来自0.19/0.20/0.21已保存记录，交付按0.21.1离线检查。N16沿用原三条及有效补复核，不重新生成；Pro对照失败只留历史，不替换有效Flash回复。J01第三条组成指代与J02内部口径仍有编辑限制，不能把可复制等同全部愿意直发。脚本重复运行不覆盖已有客户或草稿，正常使用不必载入任何示例。

旧load_current_demo.py和load_saved_demo.py分别为0.19.0/0.16.3历史回放；当前演示按上面的load_submission_demo.py操作。源码未附运行中的数据库，首次启动自行建立data。端口占用时可在本地.env改PORT，或使用`PORT=8766 python3 app.py`；不要停止别的应用来抢端口。

本机OCR依赖macOS Vision与Swift；其他平台可使用文字及保存回放。没有登录、云同步、真实库存/订单接口、自动发送微信，不是生产CRM。未收录的手机型号不会假装查过；有限官方型号资料与派生依据共用给生成和复核。

本轮干净解压使用本机已有Pillow验证，不宣称在全新机器上实测安装依赖。源码排除key、所有.env文件、运行客户库、缓存和保密题目原件。正常生成仍为Flash，Pro没有接入；本轮打包没有新增模型调用。
