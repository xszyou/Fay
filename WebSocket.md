## 消息格式

通讯地址: [`ws://127.0.0.1:10002`](ws://127.0.0.1:10002)



### 发送情绪值

```json
{
    "Topic": "Unreal",
    "Data": {
        "Key": "mood",
        "Value": 1.0
    }
}
```



| 参数       | 描述   | 类型  | 范围    |
| ---------- | ------ | ----- | ------- |
| Data.Value | 情绪值 | float | [-1, 1] |





### 发送音频

```json
{
    "Topic": "Unreal",
    "Data": {
        "Key": "audio",
        "Value": "C:\samples\sample-1.mp3",
        "Time": 10,
        "Type": "interact"
    }
}
```



| 参数       | 描述             | 类型  | 范围            |
| ---------- | ---------------- | ----- | --------------- |
| Data.Value | 音频文件绝对路径 | str   |                 |
| Data.Time  | 音频时长 (秒)    | float |                 |
| Data.Type  | 发言类型         | str   | interact/script |





### 发送回复文字

```json
{
    "Topic": "Unreal",
    "Data": {
        "Key": "text",
        "Value": "很高兴见到你"
    }
}
```



| 参数       | 描述             | 类型  | 范围            |
| ---------- | ---------------- | ----- | --------------- |
| Data.text | 文本 | str   |                 |