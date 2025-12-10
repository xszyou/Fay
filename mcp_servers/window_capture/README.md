# Window Capture MCP Server

在 Windows 上按窗口标题（或句柄）截图的 MCP 服务器，提供两个工具：
- `list_windows`：列出当前顶层窗口，可按关键词过滤。
- `capture_window`：按窗口标题关键字或句柄截屏，返回 PNG（同时保存到本地）。

## 准备
1. 进入本目录：`cd mcp_servers/window_capture`
2. 安装依赖：`pip install -r requirements.txt`（需要 Pillow；仅支持 Windows）

默认保存目录：`cache_data/window_captures`（相对仓库根目录，可在调用时通过 `save_dir` 自定义）。

## 运行
```bash
python mcp_servers/window_capture/server.py
```
或在 Fay 的 MCP 管理页面添加一条记录：
- transport: `stdio`
- command: `python`
- args: `["mcp_servers/window_capture/server.py"]`
- cwd: 仓库根目录或留空

## 工具参数
- `list_windows`
  - `keyword` (可选): 标题关键字，模糊匹配，不区分大小写。
  - `include_hidden` (可选): 是否包含隐藏/最小化窗口，默认 false。
  - `limit` (可选): 最大返回数量，默认 20，0 表示不限制。
- `capture_window`
  - `window` (必填): 窗口标题关键字，或窗口句柄（十进制/0x16 进制）。
  - `include_hidden` (可选): 允许捕获隐藏/最小化窗口，默认 false。
  - `save_dir` (可选): 自定义保存路径。

返回内容：
- 文本摘要（JSON 字符串，包含窗口信息与保存路径）。截图文件保存在 `cache_data/window_captures` 或自定义 `save_dir`。
