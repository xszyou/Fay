# Live2D 模型制作要求

本文档用于指导外包人员制作 Live2D 模型，确保交付后能直接对接我方的数字人系统。

---

## 一、技术规格

| 项目 | 要求 |
| --- | --- |
| Cubism 版本 | **Cubism 5**（SDK for Web 5-r.4） |
| model3.json 版本 | Version: 3 |
| 贴图尺寸 | 2048×2048，张数不限 |
| 交付格式 | 完整的 Cubism 导出目录（含 .moc3、贴图、motion3.json、exp3.json、physics3.json、pose3.json 等） |
| 渲染目标 | 浏览器端 WebGL（Cubism SDK for Web） |

---

## 二、必需参数（Parameters）

模型必须包含以下标准参数，参数 ID 请严格使用 Cubism 默认命名：

### 口型同步（必需）

| 参数 ID | 用途 | 说明 |
| --- | --- | --- |
| `ParamMouthOpenY` | 嘴巴张合 | **最关键参数**，程序通过此参数驱动实时口型同步 |

程序会在 `model3.json` 的 `Groups` 中查找 `LipSync` 组：

```json
{
  "Target": "Parameter",
  "Name": "LipSync",
  "Ids": ["ParamMouthOpenY"]
}
```

### 眨眼（必需）

| 参数 ID | 用途 |
| --- | --- |
| `ParamEyeLOpen` | 左眼开合 |
| `ParamEyeROpen` | 右眼开合 |

程序会在 `Groups` 中查找 `EyeBlink` 组：

```json
{
  "Target": "Parameter",
  "Name": "EyeBlink",
  "Ids": ["ParamEyeLOpen", "ParamEyeROpen"]
}
```

### 头部与身体跟随（必需）

| 参数 ID | 用途 |
| --- | --- |
| `ParamAngleX` | 头部左右旋转 |
| `ParamAngleY` | 头部上下旋转 |
| `ParamAngleZ` | 头部倾斜 |
| `ParamBodyAngleX` | 身体左右摇摆 |
| `ParamEyeBallX` | 眼球水平跟随 |
| `ParamEyeBallY` | 眼球垂直跟随 |

这些参数用于呼吸动效和鼠标/视线跟随，程序会自动驱动。

---

## 三、口型同步（LipSync）要求

程序会通过 `ParamMouthOpenY` 参数实时驱动嘴巴开合，模拟说话口型。该参数的值范围是 **0（闭嘴）~ 1（张嘴最大）**。

### 对嘴部建模的要求

- **`ParamMouthOpenY` = 0 时**：嘴巴完全闭合，自然状态
- **`ParamMouthOpenY` = 1 时**：嘴巴张到最大
- 中间值（0.2~0.8）应有平滑的过渡，不能出现跳变或形变异常
- 嘴部形变需要在 0~1 全范围内看起来自然，因为程序会输出各种中间值

### 建模细节建议

程序内部使用 OVR LipSync 的 15 种 viseme（口型音素），每种映射到不同的开合度：

| 开合度范围 | 对应口型场景 | 对应 viseme 示例 |
| --- | --- | --- |
| 0.0 | 静音 / 闭嘴 | sil |
| 0.2~0.3 | 轻微张嘴（双唇音、唇齿音） | PP, FF, nn |
| 0.4~0.5 | 中度张嘴（齿音、舌音） | TH, DD, CH, SS, ih |
| 0.6~0.7 | 较大张嘴（元音、圆唇音） | kk, E, oh |
| 0.8~0.9 | 大张嘴（低元音、圆唇突出） | aa, ou |

请确保这些开合度值下嘴型看起来合理自然。

### 重要约束

- 动作（motion）和表情（expression）中**都不要**对 `ParamMouthOpenY` 设置关键帧，否则会与程序的实时口型驱动冲突
- 如果嘴部有多个参数（如 `ParamMouthForm` 控制嘴型宽窄），可以保留，但 `ParamMouthOpenY` 必须留给程序独占

---

## 四、动作（Motions）要求

### 动作组结构

模型必须包含以下两个动作组：

| 动作组名称 | 用途 | 说明 |
| --- | --- | --- |
| `Idle` | 待机动作 | 无对话时循环播放，至少 1 个 |
| `TapBody` | 语义动作 | 对话时由程序调用，按编号索引触发 |

### TapBody 动作清单

`TapBody` 组中的动作按**数组下标**（从 0 开始）索引触发。程序会根据后端传来的语义信号选择对应编号的动作。

需要制作以下 **18 类语义动作**，每类至少 1 个，推荐关键类别提供 2 个变体（用于强度区分）：

| 编号 | 语义（behavior） | 动作描述 | 建议变体数 |
| --- | --- | --- | --- |
| 1 | nod（点头） | 轻微点头表示肯定 | 2（轻/重） |
| 2 | invite（邀请） | 伸手引导方向 | 1 |
| 3 | wave（挥手） | 挥手打招呼或告别 | 1 |
| 4 | reject（拒绝） | 摇头或摆手表示否定 | 2（轻/重） |
| 5 | think（思考） | 手托下巴、目光偏移 | 2（轻/重） |
| 6 | question（疑问） | 歪头、挑眉表示好奇 | 1 |
| 7 | explain（解释） | 双手摊开或单手比划说明 | 2（简述/详述） |
| 8 | recommend（推荐） | 单手指向或展示推荐姿态 | 1 |
| 9 | summary（总结） | 双手合拢或归拢手势 | 1 |
| 10 | wait（等待） | 双手交叠、微微前倾 | 1 |
| 11 | remind（提醒） | 食指轻点或举手提示 | 1 |
| 12 | warn（警告） | 严肃摆手或交叉手势 | 1 |
| 13 | thanks（感谢） | 鞠躬或双手合十 | 2（轻/重） |
| 14 | apology（道歉） | 鞠躬或低头表示歉意 | 1 |
| 15 | care（关心） | 微微前倾、温和手势 | 1 |
| 16 | celebrate（庆祝） | 举手欢呼、拍手 | 2（轻/重） |
| 17 | surprise（惊讶） | 后仰、手捂嘴或张大眼 | 1 |
| 18 | sad（悲伤） | 低头、肩膀下沉 | 2（轻/重） |

**关于编号与变体的说明：**

- TapBody 组中的动作按数组顺序排列，程序通过下标调用
- 有 2 个变体的类别：下标靠前的是**轻度版本**（intensity 低时使用），下标靠后的是**强度版本**（intensity 高时使用）
- 最终动作总数取决于变体数量，预计 **18~26 个**
- 交付时请提供一份**动作编号与语义的对照表**，方便我方配置映射

### 动作制作要求

- 每个动作 `FadeInTime` 和 `FadeOutTime` 建议设为 `0.5` 秒
- 动作时长建议 2~4 秒，不要过长（对话过程中会频繁切换）
- 动作结束后应能自然过渡回待机姿态
- **动作中不要包含嘴部参数的关键帧**，口型由程序实时驱动，动作中写入嘴部数据会产生冲突

---

## 五、表情（Expressions）要求

表情用于控制面部细节（眉毛、眼睛、嘴角等），与动作独立叠加。

### 必需表情清单

至少制作以下 **6 个表情**，表情名称请严格按下表命名：

| 表情名称 | 语义（affect） | 面部特征描述 |
| --- | --- | --- |
| `F01` | 默认 / 微笑（smile, warm, neutral） | 自然微笑，嘴角上扬，眉毛放松。这是最常用的表情 |
| `F02` | 严肃（serious） | 眉毛微蹙，嘴角平或略向下，目光坚定 |
| `F03` | 悲伤 / 歉意（sad, sorry） | 眉毛下垂，眼睛微眯，嘴角下拉 |
| `F04` | 好奇 / 惊讶 / 兴奋（curious, surprised, excited） | 眉毛上挑，眼睛睁大 |
| `F05` | 害羞 / 不好意思 | 脸红、目光偏移、嘴角含笑（可选，备用） |
| `F06` | 得意 / 自信 | 眉毛上扬、嘴角上翘、目光明亮（可选，备用） |

**说明：**

- `F01`~`F04` 为**必需**，程序核心逻辑依赖这 4 个表情
- `F05`~`F06` 及更多为**可选**，交付后我方可扩展映射
- 如果能做更多差异化表情更好，但命名请保持 `F01`、`F02`... 的编号格式
- 表情文件格式为 `.exp3.json`，放在 `expressions/` 目录下

### 表情制作要求

- **表情中不要包含 `ParamMouthOpenY` 参数**，口型由程序实时驱动，表情中写入会产生冲突
- 表情是对基础状态的差值叠加，请确保各表情之间切换自然
- `F01`（微笑）是默认表情，对话结束后会自动恢复到此表情

---

## 六、model3.json 结构要求

最终交付的 `model3.json` 需要包含以下结构（以示例名 `MyModel` 为例）：

```json
{
  "Version": 3,
  "FileReferences": {
    "Moc": "MyModel.moc3",
    "Textures": ["MyModel.2048/texture_00.png"],
    "Physics": "MyModel.physics3.json",
    "Pose": "MyModel.pose3.json",
    "Expressions": [
      { "Name": "F01", "File": "expressions/F01.exp3.json" },
      { "Name": "F02", "File": "expressions/F02.exp3.json" },
      { "Name": "F03", "File": "expressions/F03.exp3.json" },
      { "Name": "F04", "File": "expressions/F04.exp3.json" }
    ],
    "Motions": {
      "Idle": [
        { "File": "motions/idle.motion3.json", "FadeInTime": 0.5, "FadeOutTime": 0.5 }
      ],
      "TapBody": [
        { "File": "motions/m01_nod_light.motion3.json", "FadeInTime": 0.5, "FadeOutTime": 0.5 },
        { "File": "motions/m02_nod_heavy.motion3.json", "FadeInTime": 0.5, "FadeOutTime": 0.5 },
        "... 按照对照表顺序排列所有动作"
      ]
    }
  },
  "Groups": [
    {
      "Target": "Parameter",
      "Name": "EyeBlink",
      "Ids": ["ParamEyeLOpen", "ParamEyeROpen"]
    },
    {
      "Target": "Parameter",
      "Name": "LipSync",
      "Ids": ["ParamMouthOpenY"]
    }
  ],
  "HitAreas": [
    { "Id": "HitArea", "Name": "Head" },
    { "Id": "HitArea2", "Name": "Body" }
  ]
}
```

---

## 七、目录结构示例

```
MyModel/
├── MyModel.model3.json          # 模型配置（入口文件）
├── MyModel.moc3                 # 模型数据
├── MyModel.physics3.json        # 物理演算
├── MyModel.pose3.json           # 姿态配置（可选）
├── MyModel.cdi3.json            # 显示信息（可选）
├── MyModel.2048/                # 贴图目录
│   ├── texture_00.png
│   └── texture_01.png           # 如有多张
├── expressions/                 # 表情文件
│   ├── F01.exp3.json
│   ├── F02.exp3.json
│   ├── F03.exp3.json
│   └── F04.exp3.json
└── motions/                     # 动作文件
    ├── idle.motion3.json
    ├── m01_nod_light.motion3.json
    ├── m02_nod_heavy.motion3.json
    └── ...
```

---

## 八、交付清单

| 交付物 | 必需 | 说明 |
| --- | --- | --- |
| 完整模型导出目录 | 是 | 包含上述所有文件 |
| 动作编号对照表 | 是 | 说明 TapBody 中每个下标对应的语义和动作描述 |
| Cubism Editor 工程源文件（.cmo3） | 推荐 | 方便后续调整 |
| 动作源文件（.can3） | 推荐 | 方便后续调整动作 |

---

## 九、重要注意事项

1. **口型参数独占**：`ParamMouthOpenY` 由程序实时驱动口型同步，动作和表情中**都不要**对此参数设置关键帧
2. **表情命名必须匹配**：表情名称必须是 `F01`、`F02`... 格式，程序按此名称调用
3. **动作组命名必须匹配**：待机组必须叫 `Idle`，语义动作组必须叫 `TapBody`
4. **TapBody 的顺序很重要**：程序按数组下标索引动作，请务必按对照表排列顺序
5. **动作不宜过长**：对话场景中动作切换频繁，单个动作建议 2~4 秒
6. **Groups 配置不能遗漏**：`EyeBlink` 和 `LipSync` 两个 Group 必须在 model3.json 中正确声明
