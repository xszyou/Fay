<div align="center">
    <br>
    <img src="images/icon.png" alt="Fay" />
    <h1>Fay开源数字人框架</h1></div>





                   

如果你需要的是一个人机交互的数字人助理（当然，你也可以命令它开关设备）或者需要把数字人集成到你的产品上，请移步 [`助理完整版`](https://github.com/TheRamU/Fay/tree/fay-assistant-edition)

如果你需要是一个可以自主决策、主动联系主人的agent，请移步[`agent版`](https://github.com/TheRamU/Fay/tree/fay-agent-edition)

如果你需要是一个线上线下的销售员，请移步[`带货完整版`](https://github.com/TheRamU/Fay/tree/fay-sales-edition)    

使用文档：https://qqk9ntwbcit.feishu.cn/wiki/space/7321626901586411523



“用数字人去改变成熟传统软件的交互逻辑”

Fay数字人2024.10.09更新：

🌟Fay-助理版

1、 优化文字沟通接口的流式输出逻辑

-- fay的文字沟通接口，按标点符号切割并通过http stream返回，这样做语音合成时，能够完整处理每个断句的语音情绪。

2、 去掉内置ngrok.cc内网穿透代码

-- ngrok内网穿透可以让普通pc当作服务器使用，让移动端或者智能设备随时与fay通讯。如需继续使用可以外部启动ngrok或者其他穿透客户端，效果是一样的。

3、优化ASR处理速度

-- VAD（语音活动检测）时间由700ms减小到200ms，可以降低fay识别到我们已经说完一句话的时间，从而让fay更快作出响应

4、优化TTS速度

-- azure不使用ssml明显加速，使用azure tts平均时间可以减小700ms以上

-- 修复本地播放完声音再发送音频给数字人的bug，可以让面板播放音频更快让数字人作出响应（虽然不太可能本地播放和数字人播放同时使用）

-- 语音合成之前替换掉“*”，这是大语言模型经常作出的返回，非常影响语音合成的用户体验

5、优化Q&A文件的应用逻辑

-- 文件格式由excel更换成csv，可以更好兼容linux环境

-- 配置上Q&A文件之后会自动缓存大语言模型回复，相同对话的回复时间可以降到1ms以下

-- csv的第3列可以配置执行脚本，可以实现RPA操作或对智能硬件的控制

6、完善是否做语音合成的逻辑

-- 只有在需要发送远程音频或者发送给数字人或者面板播放时才合成音频，避免资源的浪费

7、修正多用户同时与fay聊天时qa日志有可能混乱的问题

8、 修复fay_core.py上的变量（usernmae）错识导致的远程音频传输出错

9、修复pygame init时无扬声器导致出错

10、去掉面板出现了"完成!"、“远程音频设备连接上”、“远程音频输入输出设备已经断开”、“服务已关闭！”等不必要的日志信息

🌟Fay-UE5：

- 5.4工程，与fay的对接方式更新为流式对接

--会从fay小段文字接收然后做tts处理，这样可以更快速作出响应。



更多更新日志：https://qqk9ntwbcit.feishu.cn/wiki/UlbZwfAXgiKSquk52AkcibhHngg

联系我们，请关注微信公众号 Fay数字人 

