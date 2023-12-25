[`English`](https://github.com/TheRamU/Fay/blob/main/README_EN.md)

<div align="center">
    <br>
    <img src="images/icon.png" alt="Fay">
    <h1>FAY</h1>
	<h3>Fay数字人框架 助理版</h3>
</div>



助理版是Fay 数字人框架最常用的版本。它提供了灵活的模块化设计，使开发人员能够定制和组合各种功能模块，包括情绪分析、NLP处理、语音合成和语音输出等。助理版构建的是一问（远程或本地，移动或PC，语音或文字）一答（数字人或机器，移动或PC，语音或文字或RPA）的标准模式。



如果你需要是一个线上线下的销售员，请移步[`带货完整版`](https://github.com/TheRamU/Fay/tree/fay-sales-edition)  

如果你需要是一个可以自主决策、主动联系主人的agent，请移步[`agent版`](https://github.com/TheRamU/Fay/)                      

## **Fay数字人助理版**



![](images/controller.png)

助理版使用：语音沟通，语音和文字回复；文字沟通，文字回复;对接UE、live2d、xuniren，需关闭面板播放。


## **一、模块的组成**




  Remote Android　　　　　　Local PC　　　　　Remote PC

　　　　　└─────────────┼─────────────┘
                
                
　　　　　　Aliyun API ─┐　　　│
      
            
　　　　　 　　　　　　├── ASR　　　
            
            
 　  　　 　　　 [FunASR](https://www.bilibili.com/video/BV1qs4y1g74e) ─┘  　　  │　　 　 ┌─ Yuan 1.0
                
　　　　　　　　　　　　　　　│　　 　 ├─ [LingJu](https://www.bilibili.com/video/BV1NW4y1D76a/)
                
　　　 　　　　　　　　　　　NLP ────┼─ GPT/FastGPT
                
　　　　　　　　　　　　　　　│　　 　 ├─ [Rasa+ChatGLM-6B](https://www.bilibili.com/video/BV1D14y1f7pr)
         
　　　　　　　　 Azure ─┐　 　 │　　 　 ├─ [VisualGLM](https://www.bilibili.com/video/BV1mP411Q7mj)
            
　　　　　 　 Edge TTS ─┼──     TTS 　  　 └─ [RWKV](https://www.bilibili.com/video/BV1yu41157zB)
       
　 　　 　   　　[开源 TTS](https://www.bilibili.com/read/cv25192534) ─┘　  　│　　 　 
            
　　　　　　　　　　　　　　　│　　 　 
         
　　　　　　　　　　　　　　　│　　 　 
                
　　　  ┌──────────┬────┼───────┬─────────┐

Remote Android　　[Live2D](https://www.bilibili.com/video/BV1sx4y1d775/?vd_source=564eede213b9ddfa9a10f12e5350fd64)　　 [UE](https://www.bilibili.com/read/cv25133736)　　　 [xuniren](https://www.bilibili.com/read/cv24997550)　　　Remote PC



重要：Fay（服务端）与数字人（客户端）的通讯接口: [`ws://127.0.0.1:10002`](ws://127.0.0.1:10002)（已接通）

消息格式: 查看 [WebSocket.md](https://github.com/TheRamU/Fay/blob/main/WebSocket.md)


## **二、安装说明**


### **环境** 
- Python 3.9、3.10
- Windows、macos、linux

### **安装依赖**

```shell
pip install -r requirements.txt
```

### **配置应用密钥**
+ 将应用密钥填入 `./system.conf` 中

### **启动**
启动Fay控制器
```shell
python main.py
```


### **启动数字人（非必须）**
启动数字人[xszyou/fay-ue5: 可对接fay数字人的ue5工程 (github.com)](https://github.com/xszyou/fay-ue5)


### **启动android 连接器（非必须）**
代码地址：https://github.com/xszyou/fay-android


## **三、使用说明**


### **使用说明**

+ 语音助理：Fay（麦克风输入源开启）；
+ 远程语音助理：Fay + 远程设备接入；
+ 数字人互动：Fay（麦克风输入源开启、填写性格Q&A）+ 数字人；


### **语音指令**

| 关闭核心                  | 静音                       | 取消静音                                                         |
| ------------------------- | -------------------------- | ------------------------------------------------------------ |
| 关闭、再见、你走吧   | 静音、闭嘴、我想静静        |   取消静音、你在哪呢、你可以说话了                            |



### **联系**

**商务QQ: 467665317**

**交流群及资料教程**关注公众号 **fay数字人**（**请先star本仓库**）

![](images/gzh.jpg)
