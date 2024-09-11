<div align="center">
    <br>
    <img src="images/icon.png" alt="Fay" />
    <h1>Fay开源数字人框架</h1></div>





如果你需要是一个线上线下的销售员，请移步[`带货完整版`](https://github.com/TheRamU/Fay/tree/fay-sales-edition)                       

如果你需要的是一个人机交互的数字人助理（当然，你也可以命令它开关设备），请移步 [`助理完整版`](https://github.com/TheRamU/Fay/tree/fay-assistant-edition)

如果你需要是一个可以自主决策、主动联系主人的agent，请移步[`agent版`](https://github.com/TheRamU/Fay/tree/fay-agent-edition)

框架文档：https://qqk9ntwbcit.feishu.cn/wiki/space/7321626901586411523



“所有产品都值得用数字人从新做一遍”

Fay数字人2024.09.11更新：

🌟Fay-助理版:

1、删除多余文件：datas、ppn；

2、修改readme图片路径；

3、补充注释；

4、删除多余代码；

5、docker文件整理；

6、http验证文件修改；

7、优化音频处理时间。

Fay数字人2024.09.04更新：

🌟Fay-助理版&带货版&agent版：

1、websocket服务端连接优化； 

2、接入gptsovits v3接口。）

🌟Fay-UE5.4：

1、解决插件AZSpeech在5.4SoundWave无法播放问题；

2、支持连接网页端。

Fay数字人2024.08.28更新：

🌟Fay-助理版：

1、ui上多用户对话支持（统一用户管理接口）
2、添加http验证

🌟fay-android、python-connector

1、统一音频格式wav

🌟duix sdk

1、增加音频播放状态检测（工程包已上传）

🌟Fay=ue azure版

1、5.3支持独立用户多终端与fay对接
2、降级到5.3稳定版
3、提供最新一键包
4、支持打包后配置azure key


Fay数字人2024.08.07更新：

🌟Fay-带货版：

1、统一tts输出为wav格式；
2、优化灵聚授权方式。
3、替换默认nlp为moonshot。

🌟Fay-agent版：

1、统一tts输出为wav格式。

🌟Fay-助理版：

1、统一tts输出为wav格式； 
2、优化灵聚授权方式；
3、类gpt接口，远程音频兼容多用户模式；
4、替换默认nlp为moonshot。

Fay数字人2024.07.31更新：
agent：
1、接入volcano_tts；
2、类gpt接口兼容流式方式；

助理版：
1、修复启动时配置有误问题；
 2、接入coze； 
3、接入volcano tts；
 4、类gpt接口兼容流式方式；
5、去除非3.12时报错问题。

带货版：
1、接入coze；
 2、接入volcano tts；
 3、加入记录生成到excel； 
4、加入本地违禁词检查可关闭；
5、修复gpt记录不读取问题；
6、修复缺失包问题。

Fay数字人2024.07.24更新：

🌟Fay-助理版：

1、接入SenseVoice； 

2、接入private-gpt； 

3、python3.12兼容性优化。

Fay数字人2024.07.17更新：

🌟Fay-agent版：

1、优化日程设置； 

2、优化日程提醒。

Fay数字人2024.07.10更新：

🌟Fay-助理版：

1、新增接入gptsovits；

2、修复gpt代理配置空某些base_url出现报错问题。

🌟Fay-带货版：

1、新增接入gptsovits；

2、修复gpt代理配置空某些base_url出现报错问题； 

3、页面UI优化。

🌟Fay-agent版：

1、新增接入gptsovits； 

2、修复聊天信息初始化未成功问题;

3、修复历史记录为空时报错问题。

🌟metahuman-stream对接Fay：

1、修复连接不稳定问题。

FFay数字人2024.07.03更新：

🌟Fay-agent版：

1、新增阿里云tts对接；

2、解决tts前面几个字不读的问题；

3、优化agent调用工具时递归的问题；

4、优化历史记录读取、存储问题；

5、增加自定义读取历史记录条数；

6、优化prompt逻辑；

7、优化获取结果时，误报错误问题。

🌟Fay-带货版&助理版：

1、优化授权表存储逻辑； 

2、新增阿里云tts对接； 

3、解决tts前面几个字不读的问题

4、优化百度情感分析、灵聚授权问题。

FFay数字人2024.06.26更新：

🌟Fay-agent版：

1、新增支持azure tts；

2、tts配置分离；

3、去除农业相关工具；

4、agent逻辑调整；

5、新增可接入moonshot；

6、分离知识库工具，使用需自行在工具内配置。

FFay数字人2024.06.19更新：

🌟Fay-助理版：

1. 修复langchain安装时默认包版本问题；
   
2、提供moonshot对接参考。

🌟Fay-带货版：

1. 优化入场欢迎文案；

2. 优化闲时文案；

3. 新增弹幕规范检查；

4. 新增弹幕违规检查；

5. 新增本地违禁词配置；

6. 新增违禁处理方式配置；

7. 新增弹幕格式过滤；

8. 优化请求角色定义

🌟b站弹幕监听：

1. 修复web接口初始化buvid失败的问题；

2. 移除开放平台模型的UID。


FFay数字人2024.06.12更新：

🌟Fay-agent&助理版&带货版：

优化远程音频连接和数字人连接显示。

🌟Fay-UE5：

1. 修复消息窗口消息重叠显示问题；

2. 开放azure api 区域设置。

FFay数字人2024.06.05更新：

🌟Fay-助理版：

1、增加funasr热词识别。

🌟Fay-agent版：

1、新增面板发送消息工具；

2、增加funasr热词识别。

FFay数字人2024.05.22更新：

🌟Fay-带货版：

1、调整gpt代理默认为空。

🌟Fay-agent版：

1、去除语音输出工具，改为语音输出只受“语音合成”按钮影响。

🌟Fay-助理版：

1、调整gpt代理默认为空；

2、去除funasr_wss方法；

3、rasa 支持llma3并优化接口；

4、rasa支持通过vllm部署大模型；

5、支持通过vllm部署的本地模型启动项目；

6、采用fastchat既可以降低显存，又能提升响应速度，支持主流模型部署；

7、修复类 GPT调用失败问题；

8、新增metahuman-stream对接示例 https://qqk9ntwbcit.feishu.cn/wiki/Ik1kwO9X5iilnGkFwRhcnmtvn3e

🌟Fay-UE5：

1、增加文本输入框（与Fay会同步消息），方便网页端和移动端操作。

FFay数字人2024.05.15更新：

🌟Fay-带货版：

1、新增baidu情绪分析秘钥为空时不使用情绪分析；

2、去除讯飞nlp。

🌟Fay-助理版：

1、新增baidu情绪分析秘钥为空时不使用情绪分析。

🌟Fay-UE5：

1、增加语音按钮，方便网页端和移动端操作;

2、修复ue4男模工程。

✨本期推荐学习：

1、metahuman-stream对接Fay：

https://qqk9ntwbcit.feishu.cn/wiki/Ik1kwO9X5iilnGkFwRhcnmtvn3e

FFay数字人2024.05.08更新：

🌟Fay-agent版：

1、配置项新增gpt模型配置、gpt代理默认空；

本期推荐学习：

1、【在Fay接入ufo执行任务】 https://www.bilibili.com/video/BV1rJ4m1P7Ee/

文档：https://qqk9ntwbcit.feishu.cn/wiki/BX2gw9r8JicKLukGbOZcs9YdnGh

FFay数字人2024.04.22更新：

🌟Fay-带货版：

1、使用百度情感分析替换讯飞；

 2、优化白屏问题。

🌟Fay-助理版：

1、使用百度情感分析替换讯飞；

2、优化白屏问题。

3、利用vllm对大模型进行加速推理，提升响应时间;

4、修改rasa对接ChatGLM3-6b模型支持，也可以单独接入ChatGLM3-6B，可以让ChatGLM3-6b提供与openai完全一样的接口。

🌟Fay-agent版：

1、优化获取网页内容工具的兼容性问题；

2、新增gpt代理配置；

3、优化白屏问题。

FFay数字人2024.04.15更新：

🌟Fay-agent版：

1. 前端禁止开启后修改；
   
2. 提高funasr的稳定性。

🌟Fay-助理版：

1. 精简nlp模块；
   
2. azure声音模型列表载入方式修改；
   
3.  增加自动重新载入知识库； 
   
4.  提高funasr的稳定性； 

5.  前端禁止开启后修改；

6.  增加文字回复也可以声音输出。

🌟Fay-带货版：

1. nlp模块精简；
 
2. azure声音模型列表载入方式修改；

3. 前端禁止开启后修改。

FFay数字人2024.04.08更新：

🌟Fay-agent版：

1. 优化gpt兼容接口（为ue新工程架构准备）。

🌟Fay-助理版：

1. *支持azure最新情感音频；
   
2. 优化gpt兼容接口（为ue新工程架构准备）。

🌟Fay-带货版：

1. *支持azure最新情感音频。

✨本期推荐学习：

1、【FFay数字人的ue表情制作-哔哩哔哩】 https://b23.tv/QbOMQQ7

2、【FFay数字人通过RAG方式管理知识库-哔哩哔哩】 https://b23.tv/iTsJPLO



FFay数字人2024.04.01更新：

🌟Fay-agent版：

增加agent工具：连接本地知识库（pdf）查询、获取网页内容；

🌟Fay-助理版：

1、去除已暂停使用的代码 

2、新增langchain连接本地知识库（pdf）查询

🌟Fay-带货版：

去除已暂停使用的代码 

FFay数字人2024.03.25更新：

🌟Fay-agent版：

1、增加agent工具：python执行器、网页检索器；

🌟bilibili弹幕监听：

1、修复兼容性问题

FFay数字人2024.03.18更新：

🌟Fay-带货版：

1、问答优先级调整 

🌟Fay-助理版：

1、问答优先级调整 

2、新增接入langchain nlp模块

3、新增输出问题前必须开启服务提醒

🌟Fay-agent版：

1、清除情绪计算的内容；

FFay数字人2024.03.11更新：

🌟Fay-agent版：

1、取消重启重置日程功能； 

2、上传主动发送微信消息tool(未引入)。

🌟Fay-ue5：[入口](https://github.com/xszyou/fay-ue5)

1、发布5.3模型。

✨本期推荐阅读：

1、[让agent主动给微信发送消息_哔哩哔哩_bilibili](https://www.bilibili.com/video/BV1fx421y7tz/)

2、[老ue工程补充打断功能_哔哩哔哩_bilibili](https://www.bilibili.com/video/BV1RH4y157pX/)



FFay数字人2024.03.04更新：

🌟Fay-助理版：

1、去除live2d显示，优化白屏问题；

2、集成funASR最新版本

🌟Fay-agent版：

1、优化prompt；

2、去除llm chain逻辑，减少agent与llm chain切换的token浪费；

3、优化“思考中...”log，方便后续数字人设计更友好的交互逻辑。

4、集成funASR最新版本



FFay数字人2024.02.27更新：

🌟Fay-助理版：

1、新增通义星辰nlp对接。



FFay数字人2024.02.19更新：

🌟Fay-Android连接器：

1、优化通知弹出逻辑。

🌟Fay-agent版：

1、增强funasr稳定性。



FFay数字人2024.02.05更新：

🌟Fay-助理版：

1、新增tts合成开关；

2、调整对话内容存储逻辑；

3、增强funasr稳定性;

4、修复更新情绪有误问题;

5、普通唤醒模式取消唤醒词去除。

🌟Fay-agent版：

1、解决聊天记录存储线程同步问题;

2、✨新增tts合成开关；

3、增强funasr稳定性；

4、增加开启服务提醒；

5、fay.db记录上区分agent还是llm回应;

6、✨更换最新model gpt-4-0125-preview ;

7、✨优化聊天prompt;

8、修复agent meney里的权重fn bug;

9、删除时间查询tool;

10、执行任务触发无需在聊天窗口显示及db中保存;

11、修复删除日程bug;



🌟Fay-带货版：

1、修复版本问题导致的错误；

2、新增微信视频号监听；

3、修复更新情绪有误问题。

✨本期推荐阅读：

1、带货版接入微信视频号：https://qqk9ntwbcit.feishu.cn/wiki/DC4cwhYLoiZt2HkO2CecU3jCnGd

2、FFay数字人NLP的选择：https://qqk9ntwbcit.feishu.cn/wiki/Tz4dw6LMUidnqhkv0cvc4FZCnld

[加油]祝大家工作愉快！&[庆祝]新春快乐！



联系我们，请关注微信公众号 fFay数字人 

