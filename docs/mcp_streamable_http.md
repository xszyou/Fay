# Streamable HTTP：查询公开软件文档

Fay 的 MCP 管理页支持选择 `Streamable HTTP` 连接远程 MCP 服务。现有服务器仍默认使用 SSE；STDIO 配置方式不变。此传输复用 Python MCP SDK。如果连接提示缺少 Streamable HTTP 客户端，请在运行 Fay 的 Python 环境中执行 `python -m pip install -U mcp`。

下面通过已有的服务器工具调用接口查询 Python 官方文档。示例由 Parallel 的 George Pickett 提供，使用 [Parallel MCP setup](https://docs.parallel.ai/integrations/mcp/quickstart) 中的匿名搜索能力，无需 Parallel API key；匿名访问有速率限制。只发送示例中的公开文档问题。

## 配置与连接

启动 Fay，访问 MCP 管理页 `http://127.0.0.1:5010/Page3`，点击“添加”：

| 配置项 | 值 |
| --- | --- |
| MCP 名称 | Public documentation |
| 类型 | Streamable HTTP（远程） |
| 远程服务器 | `https://mcp.parallel.ai/mcp?tools=web_search` |
| Key | 留空 |
| 开机启动 | 不勾选 |

保存后点击“连接”，确认工具列表只有 `web_search`。选择该服务器的工具保持启用；无需配置预启动。支持认证的其他服务器可以继续使用 Key 字段发送 Bearer token。

也可以通过管理接口添加并连接相同配置：

```sh
curl -sS http://127.0.0.1:5010/api/mcp/servers \
  -H 'Content-Type: application/json' \
  -d '{"name":"Public documentation","transport":"streamable_http","ip":"https://mcp.parallel.ai/mcp?tools=web_search","key":"","autostart":false}'
```

记下响应中 `server.id`，将它填入下面的 `SERVER_ID`：

```sh
SERVER_ID=1
curl -sS -X POST "http://127.0.0.1:5010/api/mcp/servers/$SERVER_ID/connect"
curl -sS "http://127.0.0.1:5010/api/mcp/servers/$SERVER_ID/tools"
curl -sS "http://127.0.0.1:5010/api/mcp/servers/$SERVER_ID/call" \
  -H 'Content-Type: application/json' \
  -d '{"method":"web_search","params":{"objective":"How does Python asyncio.wait_for handle a timeout?","search_queries":["site:docs.python.org asyncio wait_for timeout"]}}'
```

成功时检查 `success` 为 `true`、`result.isError` 不为 `true`。搜索结果的 `result.structuredContent.results` 包含原始 `url` 和相关摘录；本例验证返回 `https://docs.python.org/3/library/asyncio-task.html`。根据该文档，`asyncio.wait_for` 超时时会取消所等待的任务并抛出 `TimeoutError`。引用回答时保留返回的官方链接。搜索结果会随时间变化。

这是管理接口到实际 MCP 服务的工具调用，不需要调用对话模型。Fay 对话中的回答仍取决于已配置的对话服务和已启用的工具。可在管理页关闭 `web_search` 或断开此服务器，停止普通工具调用；已有的预启动配置方式和启用检查保持原样。

## 验证

使用 Python 3.12，在 Fay 环境中运行聚焦测试。独立的 MCP 测试环境只需安装 `mcp==1.28.0`、`flask~=3.0.0`、`flask-cors` 和 `uvicorn<0.35`：

```sh
python -m unittest test.test_mcp_streamable_http.StreamableHttpTests -v
```

本地 SDK 测试服务器只监听回环地址，覆盖初始化、发现、指定服务器调用、禁用检查、服务不可用、Bearer token 以及原有 SSE/STDIO 路径。日志输出使用替身，配置文件写入临时目录。

以下测试显式启用网络访问，通过 Fay 的添加、连接、发现、调用接口完成同一个匿名查询，并验证返回结果中的官方原始 URL。它检查实际 HTTP 请求的 Fay User-Agent、无 Authorization/API key 头，且只允许本次连接由服务端签发的 Cloudflare cookie：

```sh
FAY_MCP_LIVE=1 python -m unittest test.test_mcp_streamable_http.AnonymousLiveTests -v
```

网络不可用、限流或搜索结果变化会使这个可选测试失败，不影响默认的本地测试。
