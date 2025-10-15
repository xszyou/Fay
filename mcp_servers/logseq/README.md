# Logseq MCP Server

基于文件系统的 Logseq 图谱操作工具，提供：

- 检索内容（标签、文本）
- 获取指定标签的 pages
- 在指定 page 写入 TODO 及文本内容
- 资源存入（assets），可选插入到指定 page
- 创建 pages

## 运行方式

在 Fay 的 MCP 管理页面中新增/启用本服务，或使用现有 `faymcp/data/mcp_servers.json` 中的配置：

- transport: `stdio`
- command: `python`
- args: `["server.py"]`
- cwd: `mcp_servers/logseq`
- env: 设置 `LOGSEQ_GRAPH_DIR` 为你的 Logseq 图谱根目录（包含 `pages/`、`journals/`、`assets/` 目录）。

也可在每次调用工具时通过 `graph_dir` 参数覆盖环境变量。

## 工具列表（名称与参数）

- `search_text`
  - query: string（必填）
  - case_sensitive: boolean（默认 false）
  - max_results: integer（默认 200）
  - graph_dir: string（可选）

- `search_tag`
  - tag: string（必填，不含#）
  - max_results: integer（默认 200）
  - graph_dir: string（可选）

- `get_pages_by_tag`
  - tag: string（必填，不含#）
  - graph_dir: string（可选）

- `append_todo_to_page`
  - page: string（必填）
  - content: string（必填）
  - level: integer（默认 0）
  - with_timestamp: boolean（默认 true）
  - graph_dir: string（可选）

- `append_text_to_page`
  - page: string（必填）
  - content: string（必填）
  - level: integer（默认 0）
  - graph_dir: string（可选）

- `create_page`
  - page: string（必填）
  - content: string（可选）
  - graph_dir: string（可选）

- `update_task_status`
  - file: string (required)
  - page: string (optional)
  - line: integer (optional; 1-based)
  - task_contains: string (optional)
  - from_status: string (optional; default TODO)
  - to_status: string (optional; default DONE)
  - graph_dir: string (optional)

- `save_asset`
  - filename: string（必填）
  - source_path: string（与 base64_data 二选一）
  - base64_data: string（与 source_path 二选一）
  - page: string（可选，若提供将在 page 追加一行 `![alt](../assets/filename)`）
  - alt: string（可选，插图说明）
  - graph_dir: string（可选）

