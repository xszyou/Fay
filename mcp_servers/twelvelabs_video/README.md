# TwelveLabs Pegasus 视频理解 MCP Server

让 Fay 的 agent 具备"看懂视频"的能力：通过 [TwelveLabs](https://twelvelabs.io) 的
Pegasus 视频理解模型对视频进行总结、问答、要点提取等，返回自然语言文本。

提供一个工具：

- `analyze_video`：对一个视频（公开 URL 或已上传的 `asset_id`）按提示词进行分析，返回文本结果。

完全可选：不配置 `TWELVELABS_API_KEY` 时该服务器不会启动，对现有功能无任何影响。

## 准备

1. 进入本目录：`cd mcp_servers/twelvelabs_video`
2. 安装依赖：`pip install -r requirements.txt`（需要 `mcp` 与 `twelvelabs>=1.2.8`）
3. 申请并设置 API key（免费额度较为慷慨）：

   ```bash
   export TWELVELABS_API_KEY="你的key"   # Windows: set TWELVELABS_API_KEY=你的key
   ```

可选环境变量：

- `TWELVELABS_MODEL`：模型名，默认 `pegasus1.5`。
- `TWELVELABS_MAX_TOKENS`：默认输出 token 上限，默认 `2048`（Pegasus 1.5 最小为 512）。

## 运行

```bash
python mcp_servers/twelvelabs_video/server.py
```

或在 Fay 的 MCP 管理页面添加一条记录：

- transport: `stdio`
- command: `python`
- args: `["mcp_servers/twelvelabs_video/server.py"]`
- env: `{"TWELVELABS_API_KEY": "你的key"}`
- cwd: 仓库根目录或留空

## 工具参数

- `analyze_video`
  - `prompt` (必填): 引导分析的提示词，例如 `用一句话总结这个视频` 或 `视频里出现了哪些物体？`。
  - `video_url` (可选): 视频文件的直链 http(s) URL（与 `asset_id` 二选一）。
  - `asset_id` (可选): 已上传到 TwelveLabs 的视频 asset 的 ID（与 `video_url` 二选一）。
  - `max_tokens` (可选): 输出 token 上限，Pegasus 1.5 最小为 512，默认取 `TWELVELABS_MAX_TOKENS`。
  - `start_time` / `end_time` (可选): 只分析视频的某个时间窗口（秒，Pegasus 1.5），窗口需 ≥ 4 秒。

返回内容：模型生成的文本（总结/答案等）。

## 注意事项（来自 TwelveLabs API）

- Pegasus 1.5 **不接受**裸 `video_id`，只能用公开 URL 或上传后的 `asset_id`。
- 公开 URL 视频最大约 4GB；本地文件以 asset 方式上传上限 200MB。
- 被分析的视频/时间窗口需 ≥ 4 秒。
- 分享链接（YouTube/网盘等）不被接受，需直链媒体文件。
