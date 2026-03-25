# Fay 侧通用动作语义改造说明

## 目标

让 Fay 输出“通用动作语义”，而不是输出某个渲染引擎或某个模型的具体动作编号。

这样 Fay 可以同时服务于：

- Live2D 数字人
- 3D 数字人
- Unity / Unreal 角色
- 机器人 / 硬件角色
- 仅语音客户端

原则：

1. 保持原版 Fay WebSocket 音频接口结构不变。
2. 在原版 `Data` 中增加两个可选字段：`Action` 和 `Sentiment`。
3. Fay 不输出 `TapBody`、`MotionNo`、`F01` 这类具体实现细节。
4. 各前端或驱动端通过自己的配置表完成映射。

---

## 原版接口

原版接口如下：

```json
{
  "Topic": "human",
  "Data": {
    "Key": "audio",
    "Text": "这边请",
    "IsFirst": 1,
    "IsEnd": 0,
    "Lips": []
  }
}
```

---

## 建议改造方式

在原版 `Data` 中增加可选字段 `Action` 和 `Sentiment`：

```json
{
  "Topic": "human",
  "Data": {
    "Key": "audio",
    "Text": "这边请",
    "IsFirst": 1,
    "IsEnd": 0,
    "Lips": [],
    "Sentiment": 0.7,
    "Action": {
      "code": "guidance.invite",
      "behavior": "invite",
      "affect": "warm",
      "intensity": 0.74,
      "priority": 82
    }
  }
}
```

说明：

- 不强制增加 `ActionSchema`
- 第一版先保证字段语义稳定即可
- 如果未来需要版本控制，可以后续再补 `Action.version`
- `Action` 和 `Sentiment` 建议同时存在，但都应为可选字段

---

## 为什么需要“动作语义锚点”

这里的“动作语义锚点”，建议用 `behavior` 表示。

它的作用不是描述某个具体模型动作，而是给所有前端一个统一的“动作类别坐标”。

### 它解决的问题

| 问题 | 没有语义锚点时 | 有语义锚点时 |
| --- | --- | --- |
| Fay 与模型耦合 | Fay 需要知道 `TapBody`、`MotionNo=21` | Fay 只说 `behavior=invite` |
| 多端复用困难 | Live2D、3D、机器人都要单独写逻辑 | 各端都只做 `behavior -> 本地动作` 映射 |
| 话术很多但动作有限 | 每种话术都要单独适配 | 多个话术可归一到同一个锚点 |
| 后续维护成本高 | 每换模型都要改 Fay | 只改前端配置表 |

### 一个简单例子

这些话术：

- “这边请”
- “请进”
- “跟我来”
- “请往这边走”

在 Fay 侧都可以归一成：

```json
{
  "code": "guidance.invite",
  "behavior": "invite",
  "affect": "warm"
}
```

然后不同终端各自解释：

- Live2D：映射到某个引导动作
- 3D：映射到某个招手/邀请动画
- 机器人：映射到某个手臂引导动作
- 纯语音：忽略动作，只保留语气

所以：

- `code` 更偏业务/场景语义
- `behavior` 更偏“身体动作类别”
- `affect` 更偏“表现气质/情绪风格”

---

## 推荐字段定义

| 字段 | 类型 | 是否必填 | 含义 |
| --- | --- | --- | --- |
| `Sentiment` | number | 否 | 连续情绪值，建议范围 `-2 ~ 2` 或 `-1 ~ 1`，由接收端自行约定 |
| `Action.code` | string | 是 | 标准动作语义 ID，稳定主键 |
| `Action.behavior` | string | 否 | 动作语义锚点，描述身体动作类别 |
| `Action.affect` | string | 否 | 表现语义锚点，描述表情/语气/情绪风格 |
| `Action.intensity` | number | 否 | 强度，建议范围 `0 ~ 1` |
| `Action.priority` | number | 否 | 优先级，冲突时用于决策 |

---

## 字段职责建议

### `Sentiment`

用于表达”这段话整体情绪倾向”。

它和 `Action` 不冲突，职责不同：

- `Action` 决定”做什么”
- `Sentiment` 决定”情绪偏什么方向”

推荐用途：

- 当 `Action` 存在时，作为微调信号
- 当 `Action` 不存在时，作为回退信号
- 可同时用于表情、语气、动作幅度、TTS 风格

#### `Sentiment` 计算方式

Fay 当前有两种计算方式，按优先级依次尝试：

**方式一：百度情感分析 API（优先）**

如果配置了 `baidu_emotion_api_key` 和 `baidu_emotion_secret_key`，调用百度 NLP 的 `sentiment_classify` 接口（`ai_module/baidu_emotion.py`），返回百度原始 sentiment 值（0=消极 / 1=中性 / 2=积极）。

**方式二：本地关键词匹配（兜底）**

未配置百度 API 或调用失败时，走 `fay_core.py` 中的 `__analyze_sentiment_by_keywords()` 方法，逻辑如下：

1. 维护 4 个关键词列表，每个对应一个权重：

   | 列表 | 示例关键词 | 权重 |
   | --- | --- | --- |
   | 非常积极 | 开心、太好了、完美、激动 | +2 |
   | 轻微积极 | 好、可以、没问题、欢迎 | +1 |
   | 轻微消极 | 不好、失望、烦、担心 | -1 |
   | 非常消极 | 痛苦、绝望、崩溃、气死 | -2 |

2. 统计文本中匹配的关键词数量，加权求和
3. 标点修正：`？`/`!`/`~` 加 0.3，`...`/`。。.` 减 0.3
4. 最终 clamp 到 `[-2, +2]` 范围

注意：此计算与 `Action` 中的 `sentimentHint` 字段完全独立。`sentimentHint` 是动作规则自身的情感标注，用于辅助关键词匹配；`Sentiment` 是对整句话的情感极性评估。

### `code`

用于表达“这次动作在业务上的语义是什么”。

例如：

- `greeting.hello`
- `guidance.invite`
- `dialogue.explain`
- `social.thanks`

### `behavior`

用于表达“身体动作属于哪一类”。

例如：

- `nod`
- `invite`
- `wave`
- `think`
- `warn`

它是动作语义锚点。

### `affect`

用于表达“整体表现风格是什么”。

例如：

- `smile`
- `warm`
- `neutral`
- `serious`
- `sad`
- `excited`

这个字段比 `expression` 更通用，因为它不只适用于 Live2D 表情，也可以映射到：

- 3D 面部表情
- TTS 语气风格
- 机器人灯光/屏幕表情

### `intensity`

用于表达“动作做得轻一点还是重一点”。

例如：

- `0.2` 轻微点头
- `0.8` 明显邀请
- `0.95` 强烈庆祝

---

## Fay 侧只负责什么

Fay 侧只负责：

```text
文本 / 意图 / 场景 -> Action
文本 / 情绪分析 -> Sentiment
```

Fay 不负责：

```text
Action -> Live2D动作编号
Action -> 3D动画名
Action -> 机器人舵机动作
```

---

## 不建议 Fay 输出的字段

| 不建议由 Fay 输出 | 原因 |
| --- | --- |
| `MotionGroup` | 属于 конкретe 模型动作组 |
| `MotionNo` | 属于 конкретe 模型动作编号 |
| `TapBody` | 属于 конкретe Live2D 工程命名 |
| `F01/F02/F03` | 属于 конкретe 模型表情资源名 |

这些都应该由前端或驱动端自行配置。

---

## 推荐可配置映射表

Fay 侧维护一张 CSV 配置表（`config/action_rules.csv`），可直接用 Excel 打开编辑：

```text
关键词/意图 -> code/behavior/affect/intensity/priority/sentimentHint
```

CSV 格式说明：
- 第一行为表头：`code,behavior,affect,intensity,priority,sentimentHint,keywords`
- `keywords` 列中多个关键词用 `|` 分隔（避免与 CSV 逗号冲突）
- 文件编码为 UTF-8

不要把这张表写死在代码里。

### 当前规则示例

| 关键词或意图示例 | `code` | `behavior` | `affect` | `intensity` | `priority` |
| --- | --- | --- | --- | --- | --- |
| 你好、您好、hello、hi | `greeting.hello` | `nod` | `smile` | `0.35` | `60` |
| 欢迎、欢迎光临、欢迎来到 | `greeting.welcome` | `invite` | `warm` | `0.78` | `80` |
| 再见、拜拜、goodbye | `farewell.goodbye` | `wave` | `smile` | `0.62` | `72` |
| 是的、没错、收到、明白 | `dialogue.confirm` | `nod` | `smile` | `0.42` | `58` |
| 不是、不行、不能、no | `dialogue.reject` | `reject` | `serious` | `0.58` | `70` |
| 让我想想、考虑一下 | `dialogue.think` | `think` | `neutral` | `0.44` | `74` |
| 为什么、怎么回事、真的吗 | `dialogue.question` | `question` | `curious` | `0.52` | `55` |
| 也就是说、其实、比如 | `dialogue.explain` | `explain` | `neutral` | `0.56` | `63` |
| 建议、推荐、你可以试试 | `dialogue.recommend` | `recommend` | `smile` | `0.63` | `66` |
| 总之、综上、最后总结 | `dialogue.summary` | `summary` | `neutral` | `0.40` | `57` |
| 请进、这边请、跟我来 | `guidance.invite` | `invite` | `warm` | `0.74` | `82` |
| 稍等、等一下、请稍等 | `guidance.wait` | `wait` | `neutral` | `0.26` | `65` |
| 提醒、别忘了、记得 | `guidance.remind` | `remind` | `neutral` | `0.48` | `62` |
| 注意、小心、警告 | `guidance.warn` | `warn` | `serious` | `0.80` | `84` |
| 谢谢、感谢、多谢 | `social.thanks` | `thanks` | `warm` | `0.46` | `61` |
| 抱歉、对不起、不好意思 | `social.apology` | `apology` | `sorry` | `0.60` | `71` |
| 还好吗、没事吧、别担心 | `social.care` | `care` | `warm` | `0.50` | `64` |
| 太好了、成功了、真棒 | `emotion.celebrate` | `celebrate` | `excited` | `0.95` | `92` |
| 天啊、竟然、不会吧 | `emotion.surprise` | `surprise` | `surprised` | `0.88` | `86` |
| 难过、可惜、遗憾、糟糕 | `emotion.sad` | `sad` | `sad` | `0.82` | `83` |

说明：

- 这张表本身就建议“带上表情风格”，也就是 `affect`
- 这样前端不需要只靠 `Sentiment` 猜表情
- `Sentiment` 仍然保留，用于微调和回退

---

## 各端如何消费 `Action`

### Live2D

```text
behavior -> motion
affect -> expression
intensity -> 候选动作强度选择
sentiment -> 表情/动作幅度微调或回退
```

### 3D 数字人

```text
behavior -> 动画状态机
affect -> 面部表情 / blendshape
intensity -> 动作幅度 / 播放权重
sentiment -> 情绪层混合权重
```

### 机器人

```text
behavior -> 舵机动作模板
affect -> 灯光 / 屏幕表情 / 语音风格
intensity -> 动作幅度 / 执行力度
sentiment -> 情绪表现微调
```

### 纯语音客户端

```text
behavior -> 可忽略
affect -> TTS 风格 / 音色 / 情绪
intensity -> 情绪强度
sentiment -> 连续情绪控制
```

---

## 最小结论

Fay 侧建议从：

```json
{
  "Topic": "human",
  "Data": {
    "Key": "audio",
    "Text": "这边请",
    "IsFirst": 1,
    "IsEnd": 0,
    "Lips": []
  }
}
```

升级为：

```json
{
  "Topic": "human",
  "Data": {
    "Key": "audio",
    "Text": "这边请",
    "IsFirst": 1,
    "IsEnd": 0,
    "Lips": [],
    "Sentiment": 0.7,
    "Action": {
      "code": "guidance.invite",
      "behavior": "invite",
      "affect": "warm",
      "intensity": 0.74,
      "priority": 82
    }
  }
}
```

即可。

后续具体怎么动，由各前端或驱动端通过配置表自己决定。
