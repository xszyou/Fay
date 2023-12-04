[`中文`](https://github.com/TheRamU/Fay/blob/main/README.md)

<div align="center">
    <br>
    <img src="images/icon.png" alt="Fay">
    <h1>FAY</h1>
	<h3>Fay Digital Human Assistant</h3>
</div>


Fay Digital Human Assistant Edition is an important branch of the Fay open-source project, focusing on building open-source solutions for intelligent digital assistants. It offers a flexible and modular design that allows developers to customize and combine various functional modules, including emotion analysis, NLP processing, speech synthesis, and speech output, among others. Fay Digital Assistant Edition provides developers with powerful tools and resources for building intelligent, personalized, and multifunctional digital assistant applications. With this edition, developers can easily create digital assistants applicable to various scenarios and domains, providing users with intelligent voice interactions and personalized services.



## Fay Digital Assistant Edition

ProTip:The shopping edition has been moved to a separate branch.[`fay-sales-edition`](https://github.com/TheRamU/Fay/tree/fay-sales-edition)

![](images/controller.png)

*Assistant Fay controller use: voice communication, voice and text reply;**Text communication, text reply;**To connect UE, live2d, and xuniren, you need to close the panel for playback.*




## **Assistant Fay controller**

  Remote Android　　　　　　Local PC　　　　　Remote PC

　　　　　└─────────────┼─────────────┘
                
                
　　　　　　Aliyun API ─┐　　　│
      
            
　　　　　 　　　　　　├──      ASR　　　
            
            
 　  　　 　　　 [FunASR](https://www.bilibili.com/video/BV1qs4y1g74e) ─┘　　　│　　 　 ┌─ Yuan 1.0
                
　　　　　　　　　　　　　　　  │　　 　 ├─ [LingJu](https://www.bilibili.com/video/BV1NW4y1D76a/)
                
　　　 　　　　　　　　　　　NLP ────┼─ [GPT/ChatGPT](https://www.bilibili.com/video/BV1Dg4y1V7pn)
                
　　　　　　　　　　　　　　　│　　 　 ├─ [Rasa+ChatGLM-6B](https://www.bilibili.com/video/BV1D14y1f7pr)
         
　　　　　　　　 Azure ─┐　 　 │　　 　 ├─ [VisualGLM](https://www.bilibili.com/video/BV1mP411Q7mj)
            
　　　　　 　 Edge TTS ─┼──     TTS 　  　 └─ [RWKV](https://www.bilibili.com/video/BV1yu41157zB)
       
　   　　[Open source TTS](https://www.bilibili.com/read/cv25192534) ─┘　  │　　 　 
            
　　　　　　　　　　　　　　    │　　 　 
         
　　　　　　　　　　　　　　   │　　 　 
                
　　　 ┌──────────┬────┼───────┬─────────┐

Remote Android　　[Live2D](https://www.bilibili.com/video/BV1sx4y1d775/?vd_source=564eede213b9ddfa9a10f12e5350fd64)　　 [UE](https://www.bilibili.com/read/cv25133736)　　　 [xuniren](https://www.bilibili.com/read/cv24997550)　　　Remote PC



*Important: Communication interface between Fay (server) and digital human (client): ['ws://127.0.0.1:10002'](ws://127.0.0.1:10002) (connected)*

Message format: View [WebSocket.md](https://github.com/TheRamU/Fay/blob/main/WebSocket.md)

![](images/kzq.jpg)



**代码结构**

```
.

├── main.py	            # Program main entry
├── fay_booter.py	    # Core boot module
├── config.json		    # Controller configuration file
├── system.conf		    # System configuration file
├── ai_module
│   ├── ali_nls.py	        # Aliyun Real-time Voice
│   ├── ms_tts_sdk.py       # Microsoft Text-to-Speech
│   ├── nlp_lingju.py       # Lingju Human-Machine Interaction - Natural Language Processing
│   ├── xf_aiui.py          # Xunfei Human-Machine Interaction - Natural Language Processing
│   ├── nlp_gpt.py          # GPT API integration
│   ├── nlp_chatgpt.py      # Reverse integration with chat.openai.com
│   ├── nlp_yuan.py         # Langchao. Yuan model integration
│   ├── nlp_rasa.py         # Preceding Rasa conversation management based on ChatGLM-6B (highly recommended)
│   ├── nlp_VisualGLM.py    # Integration with multimodal large language model VisualGLM-6B
│   ├── nlp_rwkv.py         # Offline integration with rwkv
│   ├── nlp_rwkv_api.py     # rwkv server API
│   ├── yolov8.py           # YOLOv8 object detection
│   └── xf_ltp.py           # Xunfei Sentiment Analysis
├── bin                     # Executable file directory
├── core                    # Digital Human Core
│   ├── fay_core.py         # Digital Human Core module
│   ├── recorder.py         # Recorder
│   ├── tts_voice.py        # Speech synthesis enumeration
│   ├── authorize_tb.py     # fay.db authentication table management
│   ├── content_db.py       # fay.db content table management
│   ├── interact.py         # Interaction (message) object
│   ├── song_player.py      # Music player (currently unavailable)
│   └── wsa_server.py       # WebSocket server
├── gui                     # Graphical interface
│   ├── flask_server.py     # Flask server
│   ├── static
│   ├── templates
│   └── window.py           # Window module
├── scheduler
│   └── thread_manager.py   # Scheduler manager
├── utils                   # Utility modules
│   ├── config_util.py
│   ├── storer.py
│   └── util.py
└── test                    # All surprises

```





## **Upgrade Log**

**2023.12.04**

- Connect to fastgpt nlp;

- Fix the issue of abnormal lip shape reporting errors;

**2023.11.27**

- Improve the stability of websockets;

- Fix the path issue of the lip shape program;

- Improve the stability of SQLLITE.

**2023.11.20**

- Optimization and replacement of wake-up function;

- Increase yolo stability;

- Increase SQLLITE stability.

**2023.11.13**

- Fix the issue of missing wake-up word switch parameters in the configuration file;

- Fix yolo stability issues;

- New voices available for selection.

**2023.11.06**

- Update dependency packages: motion, pydub, flask~=3.0.0;

- *Adding optional sentiment analysis for motion;

- Fix bug in iFlytek sentiment analysis interface call;

- Improve the logic for saving configuration.

**2023.10.23**

- Fix the issue of digital human connection state recognition errors caused by a certain low probability;

- *Add wake-up function


**2023.09.06**

- Modification of digital person connection prompts;
- Q&A fill in demo repair;
- Fix installation package errors.

**2023.09.01**

- Fix the message logging logic of GPT and Chatglm2.

**2023.08.30**

- Adjust the message recording method of GPT;
- *Q&A supports RPA automation scripts.

**2023.08.23:**

- Replace the GPT docking method;
- Add chatglm2 docking.

**2023.08.16:**

- Optimized the issue of high system resource consumption caused by UE repeatedly reconnecting;
- Automatically control whether to start panel playback;
- Automatically delete runtime logs.

**2023.08.09:**

- Remove mp3 format warning message;
- Remove Lingju and Rwkv interface warning message;
- Optimize websocket logic;
- Optimize digital human interface communication.

**2023.08.04:**

- UE5 project updated.
- Audio-visual pixel for lip-reading is replaced by 33ms.
- Built-in rwkv_api nlp can be used directly.
- The frequency of emotional pushing to digital human terminal is reduced.
- No interface message is generated when the digital human is not connected.
- The problem that the playback information is not pushed to the digital human terminal with a certain probability due to the wrong mp3 format is fixed.
- The problem that the nlp logic is ended early when commands such as mute are executed, and the user's question message is not pushed to the digital human terminal is fixed.
- wav file startup cleaning is supplemented.
- WebSocket tool class is upgraded and improved.

**2023.07：**

+ Add runtime automatic cleaning of UI cache;
+  Add GPT proxy setting can be null;
+ Improve the stability of Lingju docking.

+ Fixed the problem of generating a large amount of WS information before connecting digital humans;
+  Add digital human (UE, Live2D, Xuniren) communication interface: real-time logs;
+ Update digital human (UE, Live2D, Xuniren) communication interface: audio push.

+ Multiple updates for the merchandise version.

+ Fixed the issue of remote voice recognition.
+ Fixed the issue of occasional unresponsiveness during ASR (Automatic Speech Recognition).
+ Removed the singing command.

+ Fixed Linux and macOS runtime errors.
+ Fixed the issue of being unable to continue execution due to lip-sync errors.
+ Provided an integration solution for RWKV.

+ Fixed an issue in Assistant Edition where text input does not read persona responses.
+ Fixed an issue in Assistant Edition where text input does not read QA responses.
+ Enhanced microphone stability.

****

+ Fixed a sound playback issue caused by the inability to run the lip-sync algorithm.

**2023.06：**

+ Refactored NLP module management logic for easier extension.
+ Split GPT into ChatGPT and GPT, replaced with a new GPT interface, and added the ability to configure proxy servers separately.
+ Specified the version of the YOLOv8 package to resolve YOLO compatibility issues.
+ Fixed self-talk bug and receiving multiple messages to be processed bug.
+ Integrated Lingju NLP API (supporting GPT3.5 and multiple applications).
+ UI corrections.
+ Integrated local lip-sync algorithm.
+ Resolved compatibility issues with multi-channel microphones.
+ Refactored fay_core.py and fay_booter.py code.
+ UI layout adjustments.
+ Restored sound selection.
+ Fixed logic for displaying "Thinking..."


## **Installation Instructions**


### **Environment** 
- Python 3.9、3.10
- Windows、macos、linux

### **Installing Dependencies**

```shell
pip install -r requirements.txt
```

### **Configuring Application Key**
+ View [API Modules](#ai-modules)
+  Browse the link, register, and create an application. Fill in the application key in `./system.conf` 

### **Starting**

Starting Fay Controller

```shell
python main.py
```


### **API Modules**

Application Key needs to be filled in before starting

| File                        | Description                                              | Link                                                         |
|-----------------------------|----------------------------------------------------------|--------------------------------------------------------------|
| ./ai_module/ali_nls.py      | Real-time Speech Recognition (*Optional*) | https://ai.aliyun.com/nls/trans                              |
| ./ai_module/ms_tts_sdk.py   | Microsoft Text-to-Speech with Emotion (*Optional*) | https://azure.microsoft.com/zh-cn/services/cognitive-services/text-to-speech/ |
| ./ai_module/xf_ltp.py       | Xunfei Sentiment Analysis(*Optional*)                     | https://www.xfyun.cn/service/emotion-analysis                |
| ./utils/ngrok_util.py       | ngrok.cc External Network Penetration (optional)          | http://ngrok.cc                                              |
| ./ai_module/nlp_lingju.py   | Lingju NLP API (supports GPT3.5 and multiple applications)(*Optional*) | https://open.lingju.ai   Contact customer service to enable GPT3.5 access |
| ./ai_module/yuan_1_0.py     | Langchao Yuan Model (*Optional*)           | https://air.inspur.com/                                              |


## **Instructions for Use**


### **Instructions for Use**

+ Voice Assistant: Fay Controller (with microphone input source enabled and panel playback enabled).
+ Remote Voice Assistant: Fay Controller (with panel playback disabled) + Remote device integration.
+ Digital Human Interaction: Fay Controller (with microphone input source enabled, panel playback disabled, and personality Q&A filled) + Digital Human.
+ Jarvis, Her: Join us to complete the experience together.


### **Voice Commands**

| Shut down                  | Mute                       | Unmute                                                         |
| ------------------------- | -------------------------- | ------------------------------------------------------------ |
| Shut down, Goodbye, Go away    | Mute, Be quiet, I want silence        |   Unmute, Where are you, You can speak now                           |



### **For business inquiries**

**business QQ **: 467665317





