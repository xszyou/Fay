# Fay 课程播放器 MCP 服务

知识库检索 MCP

面向离线知识检索，直接读取本地原生课程包（`.zip`，含 `manifest.json`），适合给第三方 agent 调用。

## 适用输入

- 原生课程包：包含 `manifest.json` 的 `.zip`（制作模式导出的课程包）
- 目录：递归扫描其中的 `.zip` 课程包

> **注意**：不支持 markdown 文件或 markdown 压缩包，仅支持原生课程包。

## 自动目录监控

- 启动时自动加载 `--source` 指定的目录 / 文件中的课程包
- 每 60 秒自动重新扫描目录，检测新增、变更、删除的 ZIP 文件并更新索引
- 可通过 `--watch-interval` 参数调整扫描间隔（秒），设为 0 可禁用

## 图片缓存与 HTTP 服务

- 搜索命中或获取章节内容时，如果该章节包含图片，会按需从课程包 ZIP 中提取到本地缓存目录
- 启动时自动开启一个轻量 HTTP 文件服务器，返回的图片字段（`images[].src`）为可直接访问的 HTTP URL
- 加载阶段不提取图片，只有实际返回给调用方的章节才会触发提取
- 参数：
  - `--cache-dir`：图片缓存目录（默认自动创建临时目录）
  - `--image-port`：HTTP 服务端口（默认 `18780`，设为 `0` 禁用图片服务）

## 设计逻辑

- 不依赖播放器运行
- 统一抽象为 `Source -> Section -> Chunk`
- 内部索引按章节、代码块、题目块建立
- 外部搜索直接接受用户原句，不要求先用 LLM 提取关键词
- 搜索结果按 `section` 聚合，直接返回完整章节内容

这套设计适合"每章就是一页 PPT"的课程知识库：

- 内部按 `chunk` 检索，召回更准
- 外部按 `section` 返回，agent 一次调用就能拿到完整知识单元

## 快速启动

直接启动：

```powershell
python mcp_server/fay_player_knowledge_base_mcp_server.py
```

预加载文件或目录（启动后自动每 60 秒扫描变化）：

```powershell
python mcp_server/fay_player_knowledge_base_mcp_server.py --source ./fay-player-guide.zip
python mcp_server/fay_player_knowledge_base_mcp_server.py --source ./exports --source ./full-course-test-demo
```

自定义扫描间隔（例如 30 秒）或禁用自动扫描：

```powershell
python mcp_server/fay_player_knowledge_base_mcp_server.py --source ./exports --watch-interval 30
python mcp_server/fay_player_knowledge_base_mcp_server.py --source ./exports --watch-interval 0
```

自定义图片缓存目录和端口：

```powershell
python mcp_server/fay_player_knowledge_base_mcp_server.py --source ./exports --cache-dir ./image_cache --image-port 19000
```

禁用图片 HTTP 服务（图片字段将保留 ZIP 内路径）：

```powershell
python mcp_server/fay_player_knowledge_base_mcp_server.py --source ./exports --image-port 0
```

使用 npm 脚本：

```powershell
npm run mcp:kb:python
```

## 工具列表

### `kb_add_source`

加载一个课程 ZIP 文件或包含课程 ZIP 的目录到内存知识库。

```json
{
  "path": "D:/courses",
  "recursive": true
}
```

### `kb_list_sources`

列出当前已加载的知识源。

### `kb_get_catalog`

查看一个 source 或全部 source 的课程目录、章节概要。

```json
{
  "source_id": "fay-player-guide-cb98e8091c"
}
```

### `kb_search`

直接使用自然语言问题搜索，并返回命中的完整章节。

返回结构包含：

- `score`
- `source_id`
- `section_id`
- `section_title`
- `matched_in`
- `snippet`
- `section`

参数：

```json
{
  "query": "MCP 默认端口是多少",
  "source_id": "fay-player-guide-cb98e8091c",
  "limit": 3,
  "include_match_details": false,
  "include_quizzes": true,
  "include_markdown": false
}
```

### `kb_get_section`

按章节 ID 或章节索引读取详细内容。

```json
{
  "source_id": "fay-player-guide-cb98e8091c",
  "section_index": 5,
  "include_quizzes": true,
  "include_markdown": false
}
```

### `kb_read_document`

读取整个 source。

`format` 可选值：

- `summary`
- `markdown`
- `text`
- `json`

### `kb_reload`

从磁盘重新加载一个 source，或重新加载全部 source。

### `kb_remove_source`

把某个 source 从当前内存会话中移除。

## 推荐调用顺序

1. `kb_list_sources`
2. 若为空，调用 `kb_add_source`
3. `kb_get_catalog`
4. `kb_search`
5. 只有在需要精确读取指定章节时再调用 `kb_get_section`
6. 如需全文，再调用 `kb_read_document`

## 搜索原理

当前实现是无依赖的轻量词法检索，不是向量检索。

- 标题完全命中优先
- 标题包含查询短语优先
- 正文包含查询短语次之
- 再结合英文 token 和中文 bigram / trigram 召回
- 若命中代码块或题目块，会额外加权
- 最后按 section 聚合分数并返回完整章节

所以第三方 agent 可以直接拿用户原句调用 `kb_search`，不必先做一轮 LLM 关键词提取。

## 接入 Fay

根据 Fay 仓库中的 MCP 知识库配置文档，这个服务适合以外部 `stdio` MCP 服务的方式接入 Fay。

推荐步骤：

1. 启动 Fay，打开 MCP 管理页：`http://127.0.0.1:5010/Page3`
2. 新增 MCP 服务
3. 传输方式选择 `stdio`
4. 启动命令填写 `python`
5. 启动参数填写：

```text
mcp_server/fay_player_knowledge_base_mcp_server.py --source ./fay-player-guide.zip
```

6. 保存并连接
7. 给 `kb_search` 配置 Prestart 参数：

```json
{
  "query": "{{question}}",
  "limit": 3,
  "include_quizzes": true
}
```

这样 Fay 会在每轮对话前先执行一次 `kb_search`，把命中的章节内容注入上下文，再交给 LLM 生成回复。

## 第三方 agent 配置示例

```json
{
  "mcpServers": {
    "fay_player_knowledge_base_mcp_server": {
      "command": "python",
      "args": [
        "mcp_server/fay_player_knowledge_base_mcp_server.py",
        "--source",
        "D:/Projects/fay-course/fay-player-guide.zip"
      ]
    }
  }
}
```

## 后续可扩展方向

- 持久化索引，避免每次启动重建
- 标签、作者、版本过滤
- embedding / rerank 检索
- `kb_answer` 这类更高层的问答封装工具
- 支持增量索引（仅重建变化文件的 chunk）
