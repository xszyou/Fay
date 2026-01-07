# MCP 工具外部调用接口

本文整理 Fay 内置 MCP 管理服务（默认端口 5010）的外部调用接口，覆盖 MCP 工具调用与预启用工具调用。

## 基础信息

- Base URL: `http://127.0.0.1:5010`
- Content-Type: `application/json`

## MCP 工具调用接口

### 调用指定服务器工具

`POST /api/mcp/servers/{server_id}/call`

请求体示例：
```json
{
  "method": "tool_name",
  "params": {
    "key": "value"
  },
  "is_prestart": false
}
```

说明：
- `is_prestart=true` 会跳过工具启用状态检查（用于预启用调用）。

### 调用工具（自动选择在线服务器）

`POST /api/mcp/tools/{tool_name}`

请求体示例：
```json
{
  "key": "value"
}
```

### 获取指定服务器工具列表

`GET /api/mcp/servers/{server_id}/tools`

### 获取在线服务器工具列表（聚合）

`GET /api/mcp/servers/online/tools`

## 预启用工具调用接口

### 配置预启用工具

`POST /api/mcp/servers/{server_id}/tools/{tool_name}/prestart`

请求体示例：
```json
{
  "enabled": true,
  "params": {
    "query": "{{question}}"
  },
  "include_history": true,
  "allow_function_call": false
}
```

### 获取可运行的预启用工具列表

`GET /api/mcp/prestart/runnable`

### 调用单个预启用工具（自动连接服务器）

`POST /api/mcp/servers/{server_id}/prestart/{tool_name}/call`

请求体示例：
```json
{
  "params": {
    "query": "{{question}}"
  },
  "question": "用户问题",
  "keep_connection": true
}
```

### 批量调用所有预启用工具（自动连接服务器）

`POST /api/mcp/prestart/call`

请求体示例：
```json
{
  "question": "用户问题",
  "keep_connection": true,
  "server_ids": [1, 2],
  "tool_names": ["tool_a", "tool_b"]
}
```

说明：
- `question` 必填，用于替换 `params` 中的 `{{question}}` 占位符。
- `server_ids` 与 `tool_names` 为空时表示对全部预启用工具生效。
