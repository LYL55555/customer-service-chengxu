# 解压后运行 · 0.16.3

评审材料可直接双击index.html阅读，无需账户。localhost地址只对运行者本机有效，不能当公网演示链接。

1. 解压SOURCE_v0.16.3.zip，进入其中CHENGXU_Source_v0.16.3文件夹。
2. 安装Python 3.10或以上；建议macOS。终端运行：

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/load_saved_demo.py
python3 app.py
```

3. 打开http://127.0.0.1:8765/。在“顾问与客户”选“提交演示 · 虚构顾问小林”，查看N21/N29/N39。标题明确“保存的真实结果”，载入过程0模型调用；历史失败也保留。可先不配key阅读、查看及选择复制。
4. 若要真实生成，在源码根目录自行新建.env，按CONFIG_TEMPLATE.txt填写地址、模型和key。不要把key填进网页或聊天，也不要对外提交.env。重启服务或刷新配置；未配置时页面会明确提示，已配置但未调用时显示尚未验证。
5. 原生复制测试：复制N21或N29第二条，粘贴到本机空白文稿核对。本轮自动化粘贴通道未能完成此项，详见D评估；不要以“已复制”提示代替实际核对。

接口使用DeepSeek官方beta严格工具模式；其他OpenAI兼容接口只保证有本地JSON检查，尚未在本轮实测。正常服务不自动重试。若要在另一端口运行，可在本地.env写PORT=18865后重启。

聊天截图的本机OCR依赖macOS及可用Swift命令行工具；其他平台可直接用已确认文字聊天和保存结果演示，不能承诺相同截图能力。新截图请使用虚构内容。

源码不含key、任何.env文件、运行客户数据库和缓存；首次运行自行建立本机data目录。保存结果演示提供的是明确虚构案例的JSON，不是从运行库导出的数据库。重复载入脚本不会覆盖已有演示资料。

