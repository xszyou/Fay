# Fay 课程知识库

本目录存放 Fay 的课程知识包（`.zip` 格式），由「课程知识库」MCP server（`mcp_servers/fay_player_knowledge/`）加载，供 Fay 在对话中检索引用。

## 课程包来源

所有课程包均可在 **[https://player.fay-agent.com](https://player.fay-agent.com)** 在线创建或浏览，主要功能：

- 🌐 **浏览 / 创建** 课程知识包
- ▶️ **在线播放** 课程内容
- 🎬 **导出视频** 一键将课程包生成讲解视频
- 📄 **导出 Markdown 文档** 将课程内容转为 md 文档
- 🆓 **完全开源** 项目地址：[https://gitee.com/xszyou/fay-player](https://gitee.com/xszyou/fay-player)

下载得到的 `.zip` 放入本目录，即可被 Fay 引用。

## 当前包含的课程

| 课程包 | 简介 |
| --- | --- |
| Fay介绍（面向开发者）.zip | Fay 数字人框架的整体架构与开发者上手指南 |
| Fay多用户对话消息分发逻辑.zip | 多用户场景下消息分发与会话隔离机制 |
| Fay的think标签处理逻辑.zip | `<think>` 标签从产生到记忆归档的全链路 |
| Fay的prestart标签处理逻辑.zip | `<prestart>` 标签的注册、调度与双通道注入 |
| OfficeEcho-course.zip | OfficeEcho 示例课程 |

## 使用方式

1. 在 [https://player.fay-agent.com](https://player.fay-agent.com) 创建或下载课程包；
2. 将 `.zip` 文件放入本目录；
3. 启动 Fay 后，「课程知识库」MCP server 会自动加载并向 Fay 暴露 `search` / `get_section` 工具；
4. 与 Fay 对话时即可让它检索这些知识。
