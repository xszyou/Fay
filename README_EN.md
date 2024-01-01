[`中文`](https://github.com/TheRamU/Fay/blob/main/README.md)

<div align="center">
    <br>
    <img src="images/icon.png" alt="Fay">
    <h1>Fay Digital Human AI Agent Version</h1>
    An "agent" is a representative that can make decisions and execute plans for you, relying on the powerful ReAct capability of the most advanced large language models.
</div>




**Please Understand First**

If you need an online and offline salesperson, please go to [`Complete Retail Version`](https://github.com/TheRamU/Fay/tree/fay-sales-edition)

If you need a digital human assistant for human-computer interaction (and yes, you can command it to switch devices on and off), please go to [`Complete Assistant Version`](https://github.com/TheRamU/Fay/tree/fay-assistant-edition)

**"Excellent products deserve to be redone with digital humans."**
1.Assistant mode based on schedule maintenance: Managing and maintaining your schedule, not just a simple alarm clock.
<img src="images/you1.png" alt="Fay">

2.Powerful planning and execution (ReAct) capability: Plan -> Execute <-> Reflect -> Summarize.
<img src="images/you2.png" alt="Fay">

3.Automatic switching between LLM Chain and React Agent: Retains planning and execution capabilities while considering chatting abilities (still needs optimization).
<img src="images/you3.png" alt="Fay">

4.Dual memory mechanism: Stanford AI Town's memory stream (time, importance, relevance) for long-term memory, and adjacent conversation memory for coherent conversations.
<img src="images/you4.png" alt="Fay">

5.Easily expandable agent tools.
<img src="images/you5.png" alt="Fay">

6.Accompanying 24-hour background running Android connector.
<img src="images/you6.png" alt="Fay">

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
2024.01.01:

OpenAI token calculation ✓
Optimized ReAct Agent and LLM Chain auto-switching logic ✓
*Added dual memory mechanism: long-term memory stream and short-term chat memory ✓
Fixed record.py ASR bug ✓
Improved stability of remote audio (Android connector) ✓
Fixed execution time calculation bug ✓
Optimized voice output logic ✓

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
