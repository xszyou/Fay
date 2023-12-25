[`中文`](https://github.com/TheRamU/Fay/blob/main/README.md)

<div align="center">
    <br>
    <img src="images/icon.png" alt="Fay">
    <h1>Fay Digital Human AI Agent Version</h1>
    An "agent" is a representative that can make decisions and execute plans for you, relying on the powerful ReAct capability of the most advanced large language models.
</div>





**Belated December announcement, the 5th edition of Fay Digital Human AI Agent Version (complete code for smart agriculture box can be requested via our public channel) is officially uploaded!**

If you need an online and offline salesperson, please go to [`Complete Retail Version`](https://github.com/TheRamU/Fay/tree/fay-sales-edition)

If you need a digital human assistant for human-computer interaction (and yes, you can command it to switch devices on and off), please go to [`Complete Assistant Version`](https://github.com/TheRamU/Fay/tree/fay-assistant-edition)

***“Exceptional products deserve to be reimagined with digital humans”***

Highlights: Proactive execution of planned tasks without the need for question-and-answer interactions, automatic planning and use of the agent tool to complete tasks; use of OpenAI TTS; use of a vector database for permanent memory and memory retrieval;

![](images/agent_demo.gif)

​                                                                       (Above image: Testing ReAct capabilities）

## **Installation Instructions**

### **System Requirements** 

- Python 3.9, 3.10
- Windows, macOS, Linux

### **Installing Dependencies**

```shell
pip install -r requirements.txt
```

### **Configuring Application Keys**

+ Enter your GPT-4 key in `./system.conf` 

### **Launching the Controller**

Start the Fay controller

```shell
python main.py
```

### **Launching the Digital Human (Optional)**

Repository URL:https://github.com/xszyou/fay-ue5


### **Launch of Android Connector (Optional)**
Repository URL: https://github.com/xszyou/fay-android


### **Changelog**
2023.12.25:

Implemented the automatic switching logic between agent ReAct and LLM chain ✓
Distinguished task messages in the chat window ✓

Fixed the bug in deleting schedules ✓

Optimized remote audio logic ✓

Introduced loading effects for pending processes ✓

Optimized prompts to resolve recursive calling issues in schedule tasks ✓

Fixed the bug in clearing one-time schedules ✓


### **Contact**

**Business QQ: 467665317**

Join the discussion group by following the public account Fay Digital Human (please star this repository first)

<img src="images/2.jpg"  />
