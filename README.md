<div align="center">
    <br>
    <img src="images/icon.png" alt="Fay" />
    <h1>Fay开源数字人框架</h1></div>





如果你需要是一个线上线下的销售员，请移步[`带货完整版`](https://github.com/TheRamU/Fay/tree/fay-sales-edition)                       

如果你需要的是一个人机交互的数字人助理（当然，你也可以命令它开关设备），请移步 [`助理完整版`](https://github.com/TheRamU/Fay/tree/fay-assistant-edition)

如果你需要是一个可以自主决策、主动联系主人的agent，请移步[`agent版`](https://github.com/TheRamU/Fay/tree/fay-agent-edition)

框架文档：https://qqk9ntwbcit.feishu.cn/wiki/space/7321626901586411523



“用数字人去改变成熟传统软件的交互逻辑”

Fay数字人2024.09.25更新：

🌟Fay-助理版:

- 重写日志系统：适配多用户逻辑下的panel、数字人端、控制台和文件；补充年月日信息。
  
- 提高代码可读性，整理代码目录区分llm、tts、asr。
  
- 修复ui显示的远程音频连接状态不更新问题。
  
- fay对旧版ue兼容性修复。
  
- 更新metahuman-stream的对接方式：https://qqk9ntwbcit.feishu.cn/wiki/Ik1kwO9X5iilnGkFwRhcnmtvn3e
  
- 修复web模式读取控制台输入出错bug
  
- 灵聚nlp接口升级支持多用户对接
  
- gpt nlp接口prompt部分接入数字人个人信息，并取消个人信息直接命中匹配
  
- coze nlp升级到v3接口
  
Fay数字人2024.09.19更新：

🌟Fay-助理版:

- 代码重构：标准化了交互代码、提高了可阅读性、删除了多余代码
  
- 数字人接口：多路并发接入支持、按用户路由支持、提高了反应速度、使用http音频地址、优化连接状态的判断逻辑
  
- 远程音频接口：多路并发接入支持、按用户路由支持、单向传输支持、提高了速度、优化连接状态的判断逻辑
  
- 文字沟通接口：多路并发接入支持、按用户路由支持
  
- ui接口：多路并发接入支持、按用户路由支持
  
- 速度提升：azure tts省去音频转换时间；由轮询交互机制更换成直接交互机制；提高了音频读取速度；去掉所有不必要的sleep；阻塞方法都使用单独线程或协程。
  
- 明确声音输出逻辑：远程音频接口是否回送依据接口参数要求；数字人接口是否推送依据接口是否被连接；本机是否播放依据本机播放声音开关是否打开。
  
- 3.12兼容性修复：websocket工具类把协程转换成任务；pyqt5更换版本。
  
- asr多路并发支持
  
- nlp多路并发支持
  
- tts多路并发（本来就）支持
  
- 修复python远程音频demo变态声音问题
  
- 修复命中qa的判断逻辑
  
- 增加控制台退出进程命令exit
  
- 优化拾音逻辑：只有在展板播放并且没有使用唤醒功能时才会停止拾音

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


更多：https://qqk9ntwbcit.feishu.cn/wiki/UlbZwfAXgiKSquk52AkcibhHngg

联系我们，请关注微信公众号 Fay数字人 

