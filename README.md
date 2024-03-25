[`English`](https://github.com/xszyou/Fay/blob/main/README_EN.md) 

<div align="center">
    <br>
    <img src="images/icon.png" alt="Fay">
    <h1>FAY</h1>
	<h3>Fay数字人框架 助理版 </h3>
</div>



助理版是Fay 数字人框架最常用的版本。它提供了灵活的模块化设计，使开发人员能够定制和组合各种功能模块，包括情绪分析、NLP处理、语音合成和语音输出等。助理版构建的是一问（远程或本地，移动或PC，语音或文字）一答（数字人或机器，移动或PC，语音或文字或RPA）的标准模式。



如果你需要是一个线上线下的销售员，请移步[`带货完整版`](https://github.com/xszyou/Fay/tree/fay-sales-edition)  

如果你需要是一个可以自主决策、主动联系主人的agent，请移步[`agent版`](https://github.com/xszyou/Fay/tree/fay-agent-edition)                      

## **Fay数字人助理版**



![](images/controller.png)

https://github.com/TheRamU/Fay/blob/main/WebSocket.md)


## **安装说明**


### **环境** 
- Python 3.9、3.10
- Windows、macos、linux

### **安装依赖**

```shell
pip install -r requirements.txt
```

### **配置应用**
+ 配置 `./system.conf` 文件

### **启动**
启动Fay控制器
```shell
python main.py
```


### **启动数字人（非必须）**
启动数字人[xszyou/fay-ue5: 可对接fay数字人的ue5工程 (github.com)](https://github.com/xszyou/fay-ue5)


### **启动android 连接器（非必须）**
代码地址：https://github.com/xszyou/fay-android


## **使用说明**


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
