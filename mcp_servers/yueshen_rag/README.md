## YueShen RAG MCP Server

扫描 `新知识库`（或自定义目录）的 pdf/docx，按段落/句子切块写入 Chroma，并提供检索工具。Embedding 配置可通过 MCP 参数或环境变量传入。

### 依赖
```bash
pip install -r requirements.txt
```
- 若有 `.doc` 请先转换为 `.docx` 再处理；当前依赖仅支持 pdf/docx。

### 环境变量（可选）
- `YUESHEN_CORPUS_DIR`：知识库原始文档目录（默认 `新知识库`）
- `YUESHEN_PERSIST_DIR`：Chroma 向量库持久化目录（默认 `cache_data/chromadb_yueshen`）
- `YUESHEN_EMBED_BASE_URL`：Embedding API base url（将拼接 `/embeddings`）
- `YUESHEN_EMBED_API_KEY`：Embedding API key
- `YUESHEN_EMBED_MODEL`：Embedding 模型名（默认 `text-embedding-3-small`）
- `YUESHEN_AUTO_INGEST`：是否启用启动即自动扫描入库（默认 1，设为 0 关闭）
- `YUESHEN_AUTO_INTERVAL`：自动扫描间隔秒（默认 300，最小 30）
- `YUESHEN_AUTO_RESET_ON_START`：启动时是否 reset 后重建索引（默认 0）

### 运行
```bash
cd mcp_servers/yueshen_rag
python server.py
```

### 添加到 Fay
- MCP 管理页面：新增服务器，transport 选 `stdio`；command 填 Python（如 `python` 或虚拟环境路径）；args `["mcp_servers/yueshen_rag/server.py"]`；cwd 指向项目根目录；如需自定义 Embedding，填入 env 的 base url / api key / model。
- 也可以直接编辑 `faymcp/data/mcp_servers.json` 添加对应项，重启 Fay MCP 服务后生效。

### 预启动推荐
- 在 MCP 页面工具列表为 `query_yueshen` 打开“预启动”，参数示例：`{"query": "{{question}}", "top_k": 4}`，用户提问会替换 `{{question}}`。
- 若希望启动后自动补扫新文档，可为 `ingest_yueshen` 配置预启动（如 `{"reset": false}` 或指定 `corpus_dir`/`batch_size` 等）。

### 工具
- `ingest_yueshen`：扫描并入库；参数 `corpus_dir`、`reset`、`chunk_size`、`overlap`、`batch_size`、`max_files`，以及可选 `embedding_base_url`/`embedding_api_key`/`embedding_model` 覆盖环境变量。
- `query_yueshen`：向量检索；参数 `query`，可选 `top_k`、`where`，以及可选 embedding 配置与 ingest 保持一致。
- `yueshen_stats`：查看向量库状态（持久化目录、集合名、向量数等）。

### 默认路径与切块
- 语料目录：`悦肾e家知识库202511/新知识库`
- 持久化目录：`cache_data/chromadb_yueshen`
- 切块：约 600 字，120 重叠，可按需调整
