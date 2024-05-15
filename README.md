<div align="center">
    <br>
    <img src="images/icon.png" alt="Fay" />
    <h1>Fay开源数字人框架</h1></div>





如果你需要是一个线上线下的销售员，请移步[`带货完整版`](https://github.com/TheRamU/Fay/tree/fay-sales-edition)                       

如果你需要的是一个人机交互的数字人助理（当然，你也可以命令它开关设备），请移步 [`助理完整版`](https://github.com/TheRamU/Fay/tree/fay-assistant-edition)

如果你需要是一个可以自主决策、主动联系主人的agent，请移步[`agent版`](https://github.com/TheRamU/Fay/tree/fay-agent-edition)

框架文档：https://qqk9ntwbcit.feishu.cn/wiki/space/7321626901586411523



“所有产品都值得用数字人从新做一遍”

Fay数字人2024.05.15更新：

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

Fay数字人2024.05.08更新：

🌟Fay-agent版：

1、配置项新增gpt模型配置、gpt代理默认空；

本期推荐学习：

1、【在Fay接入ufo执行任务】 https://www.bilibili.com/video/BV1rJ4m1P7Ee/

文档：https://qqk9ntwbcit.feishu.cn/wiki/BX2gw9r8JicKLukGbOZcs9YdnGh

Fay数字人2024.04.22更新：

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

Fay数字人2024.04.15更新：

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

Fay数字人2024.04.08更新：

🌟Fay-agent版：

1. 优化gpt兼容接口（为ue新工程架构准备）。

🌟Fay-助理版：

1. *支持azure最新情感音频；
   
2. 优化gpt兼容接口（为ue新工程架构准备）。

🌟Fay-带货版：

1. *支持azure最新情感音频。

✨本期推荐学习：

1、【Fay数字人的ue表情制作-哔哩哔哩】 https://b23.tv/QbOMQQ7

2、【Fay数字人通过RAG方式管理知识库-哔哩哔哩】 https://b23.tv/iTsJPLO



Fay数字人2024.04.01更新：

🌟Fay-agent版：

增加agent工具：连接本地知识库（pdf）查询、获取网页内容；

🌟Fay-助理版：

1、去除已暂停使用的代码 

2、新增langchain连接本地知识库（pdf）查询

🌟Fay-带货版：

去除已暂停使用的代码 

Fay数字人2024.03.25更新：

🌟Fay-agent版：

1、增加agent工具：python执行器、网页检索器；

🌟bilibili弹幕监听：

1、修复兼容性问题

Fay数字人2024.03.18更新：

🌟Fay-带货版：

1、问答优先级调整 

🌟Fay-助理版：

1、问答优先级调整 

2、新增接入langchain nlp模块

3、新增输出问题前必须开启服务提醒

🌟Fay-agent版：

1、清除情绪计算的内容；

Fay数字人2024.03.11更新：

🌟Fay-agent版：

1、取消重启重置日程功能； 

2、上传主动发送微信消息tool(未引入)。

🌟Fay-ue5：[入口](https://github.com/xszyou/fay-ue5)

1、发布5.3模型。

✨本期推荐阅读：

1、[让agent主动给微信发送消息_哔哩哔哩_bilibili](https://www.bilibili.com/video/BV1fx421y7tz/)

2、[老ue工程补充打断功能_哔哩哔哩_bilibili](https://www.bilibili.com/video/BV1RH4y157pX/)



Fay数字人2024.03.04更新：

🌟Fay-助理版：

1、去除live2d显示，优化白屏问题；

2、集成funASR最新版本

🌟Fay-agent版：

1、优化prompt；

2、去除llm chain逻辑，减少agent与llm chain切换的token浪费；

3、优化“思考中...”log，方便后续数字人设计更友好的交互逻辑。

4、集成funASR最新版本



Fay数字人2024.02.27更新：

🌟Fay-助理版：

1、新增通义星辰nlp对接。



Fay数字人2024.02.19更新：

🌟Fay-Android连接器：

1、优化通知弹出逻辑。

🌟Fay-agent版：

1、增强funasr稳定性。



Fay数字人2024.02.05更新：

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

2、Fay数字人NLP的选择：https://qqk9ntwbcit.feishu.cn/wiki/Tz4dw6LMUidnqhkv0cvc4FZCnld

[加油]祝大家工作愉快！&[庆祝]新春快乐！



联系我们，请关注微信公众号 fay数字人 

