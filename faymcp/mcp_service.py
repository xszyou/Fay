#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import json
import time
import threading
import logging
from datetime import datetime
from typing import Any, Dict, List
from flask_cors import CORS
from faymcp.mcp_client import McpClient
from faymcp import tool_registry
from utils import util



# 创建Flask应用
app = Flask(__name__)

# 添加CORS支持，允许所有来源的跨域请求
CORS(app, resources={r"/*": {"origins": "*"}})


# MCP服务器数据文件路径
MCP_DATA_FILE = os.path.join(os.path.dirname(__file__), 'data', 'mcp_servers.json')

# MCP工具状态数据文件路径
MCP_TOOL_STATES_FILE = os.path.join(os.path.dirname(__file__), 'data', 'mcp_tool_states.json')

# 确保data目录存在
os.makedirs(os.path.dirname(MCP_DATA_FILE), exist_ok=True)

# 存储MCP客户端对象的字典，键为服务器ID
mcp_clients = {}

# 存储工具状态的字典，键为服务器ID，值为工具名称->状态的字典
mcp_tool_states = {}

# 连接检查定时器
connection_check_timer = None

# 连接检查间隔（秒）
CONNECTION_CHECK_INTERVAL = 60

# 默认MCP服务器数据
default_mcp_servers = [
]

# 加载MCP服务器数据
def load_mcp_servers():
    try:
        if os.path.exists(MCP_DATA_FILE):
            with open(MCP_DATA_FILE, 'r', encoding='utf-8') as f:
                servers = json.load(f)
                # 确保所有服务器状态为离线
                for server in servers:
                    server['status'] = 'offline'
                    server['latency'] = '0ms'
                return servers
        else:
            # 如果文件不存在，使用默认数据并保存
            save_mcp_servers(default_mcp_servers)
            return default_mcp_servers
    except Exception as e:
        util.log(1, f"加载MCP服务器数据失败: {e}")
        return default_mcp_servers

# 加载MCP工具状态数据
def load_mcp_tool_states():
    try:
        if os.path.exists(MCP_TOOL_STATES_FILE):
            with open(MCP_TOOL_STATES_FILE, 'r', encoding='utf-8') as f:
                states = json.load(f)
                # 转换字符串键为整数（因为JSON中的键总是字符串）
                converted_states = {}
                for server_id_str, tools in states.items():
                    try:
                        server_id = int(server_id_str)
                        converted_states[server_id] = tools
                    except ValueError:
                        continue
                return converted_states
        else:
            return {}
    except Exception as e:
        util.log(1, f"加载MCP工具状态数据失败: {e}")
        return {}

# 保存MCP工具状态数据
def save_mcp_tool_states():
    try:
        # 转换整数键为字符串（JSON要求）
        states_to_save = {}
        for server_id, tools in mcp_tool_states.items():
            states_to_save[str(server_id)] = tools
            
        with open(MCP_TOOL_STATES_FILE, 'w', encoding='utf-8') as f:
            json.dump(states_to_save, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        util.log(1, f"保存MCP工具状态数据失败: {e}")
        return False

# 保存MCP服务器数据
def save_mcp_servers(servers):
    try:
        # 创建要保存的服务器数据副本
        servers_to_save = []
        for server in servers:
            # 创建服务器数据的副本，不包含运行状态
            server_copy = {
                "id": server['id'],
                "name": server['name'],
                "ip": server.get('ip', ''),
                "connection_time": server.get('connection_time', ''),
                "key": server.get('key', ''),  # 保存Key字段
                "transport": server.get('transport', 'sse'),
                "command": server.get('command', ''),
                "args": server.get('args', []),
                "cwd": server.get('cwd', ''),
                "env": server.get('env', {})
            }
            servers_to_save.append(server_copy)
            
        with open(MCP_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(servers_to_save, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        util.log(1, f"保存MCP服务器数据失败: {e}")
        return False

# 初始化MCP服务器数据
mcp_servers = load_mcp_servers()

# 初始化MCP工具状态数据
mcp_tool_states = load_mcp_tool_states()

# 工具状态管理函数
def get_tool_state(server_id, tool_name):
    """获取工具的启用状态，默认为True"""
    if server_id not in mcp_tool_states:
        mcp_tool_states[server_id] = {}
    return mcp_tool_states[server_id].get(tool_name, True)

def set_tool_state(server_id, tool_name, enabled):
    """设置工具的启用状态"""
    if server_id not in mcp_tool_states:
        mcp_tool_states[server_id] = {}
    mcp_tool_states[server_id][tool_name] = enabled
    # 立即保存到文件
    save_mcp_tool_states()

# 连接真实MCP服务器
def connect_to_real_mcp(server):
    """
    连接到真实的MCP服务器
    :param server: 服务器信息字典
    :return: (是否连接成功, 更新后的服务器信息, 可用工具列表)
    """
    global mcp_clients
    try:
        # 获取服务器配置
        server_id = server['id']
        transport = server.get('transport', 'sse')
        api_key = server.get('key', '')  # 获取Key
        def _enabled_lookup(tool_name: str, sid=server_id):
            return get_tool_state(sid, tool_name)

        # 如果已存在旧连接，先断开并清理（防止重复连接）
        if server_id in mcp_clients:
            try:
                old_client = mcp_clients[server_id]
                if hasattr(old_client, 'disconnect'):
                    old_client.disconnect()
                # util.log(1, f"已断开服务器 {server['name']} (ID: {server_id}) 的旧连接")
            except Exception as e:
                pass  # 静默处理断开旧连接的错误
            del mcp_clients[server_id]
        
        client = None
        if transport == 'stdio':
            # 统一默认工作目录为项目根目录（faymcp 的上一级），避免相对路径在不同启动目录下失效
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            cfg_cwd = server.get('cwd')
            cwd = cfg_cwd if (cfg_cwd and str(cfg_cwd).strip()) else repo_root
            stdio_config = {
                "command": server.get('command'),
                "args": server.get('args', []) or [],
                "cwd": cwd,
                "env": (server.get('env') or None),
            }
            client = McpClient(
                server_url=None,
                api_key=None,
                transport='stdio',
                stdio_config=stdio_config,
                server_id=server_id,
                enabled_lookup=_enabled_lookup,
            )
        else:
            ip = server.get('ip', '')
            endpoint = ip
            client = McpClient(
                endpoint,
                api_key,
                server_id=server_id,
                enabled_lookup=_enabled_lookup,
            )
        
        # 记录开始时间
        start_time = time.time()
        
        # 尝试连接并获取可用工具列表
        success, result = client.connect()
        
        # 计算延迟时间
        latency = int((time.time() - start_time) * 1000)
        
        if success:
            # 连接成功，更新服务器状态
            server['status'] = 'online'
            server['latency'] = f"{latency}ms"
            server['connection_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 保存客户端对象
            mcp_clients[server_id] = client
            
            return True, server, result
        else:
            # 连接失败，更新服务器状态
            server['status'] = 'offline'
            server['latency'] = '0ms'
            server['connection_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 如果连接失败，删除可能存在的客户端对象
            if server_id in mcp_clients:
                del mcp_clients[server_id]
            tool_registry.mark_all_unavailable(server_id)
                
            return False, server, []
    except Exception as e:
        util.log(1, f"连接MCP服务器失败: {e}")
        server['status'] = 'offline'
        server['latency'] = '0ms'
        
        # 如果连接失败，删除可能存在的客户端对象
        if server['id'] in mcp_clients:
            del mcp_clients[server['id']]
        tool_registry.mark_all_unavailable(server['id'])
            
        return False, server, []

# 获取MCP客户端
def get_mcp_client(server_id):
    """
    获取指定服务器ID的MCP客户端对象
    :param server_id: 服务器ID
    :return: McpClient对象或None
    """
    return mcp_clients.get(server_id)

# 断开所有MCP服务连接
def disconnect_all_mcp_servers():
    """
    断开所有MCP服务器连接，清理资源
    """
    global mcp_clients, mcp_servers, connection_check_timer
    
    util.log(1, f'开始断开 {len(mcp_clients)} 个MCP服务连接...')
    
    # 停止连接检查定时器
    if connection_check_timer:
        try:
            connection_check_timer.cancel()
            util.log(1, '连接检查定时器已停止')
        except Exception as e:
            util.log(1, f'停止连接检查定时器失败: {e}')
        connection_check_timer = None
    
    # 断开所有MCP客户端连接
    disconnected_count = 0
    for server_id, client in list(mcp_clients.items()):
        try:
            if hasattr(client, 'disconnect'):
                client.disconnect()
            elif hasattr(client, 'close'):
                client.close()
            disconnected_count += 1
            util.log(1, f'已断开MCP服务器连接: ID {server_id}')
        except Exception as e:
            util.log(1, f'断开MCP服务器连接失败 (ID: {server_id}): {e}')
        finally:
            tool_registry.remove_server(server_id)
    
    # 清理所有数据
    mcp_clients.clear()
    
    # 更新所有服务器状态为离线
    for server in mcp_servers:
        server['status'] = 'offline'
        server['latency'] = '0ms'
    
    # 保存服务器状态
    try:
        save_mcp_servers(mcp_servers)
    except Exception as e:
        util.log(1, f'保存MCP服务器状态失败: {e}')
    
    util.log(1, f'成功断开 {disconnected_count} 个MCP服务连接，资源已清理')

# 调用MCP服务器工具
def call_mcp_tool(server_id, method, params=None):
    """
    调用MCP服务器工具
    :param server_id: 服务器ID
    :param method: 方法名
    :param params: 参数字典
    :return: (是否成功, 结果或错误信息)
    """
    try:
        # 检查工具是否被启用
        if not get_tool_state(server_id, method):
            return False, f"工具 '{method}' 已被禁用"
        
        # 获取客户端对象
        client = get_mcp_client(server_id)
        if not client:
            return False, "未找到服务器连接"
            
        # 调用工具
        return client.call_tool(method, params)
    except Exception as e:
        util.log(1, f"调用MCP工具失败: {e}")
        return False, f"调用MCP工具失败: {str(e)}"

# 主页路由 - 直接重定向到Page3页面
@app.route('/')
def index():
    return redirect(url_for('page3'))

# MCP页面路由 - Page3.html
@app.route('/Page3')
def page3():
    # 传递MCP服务器数据到模板
    return render_template('Page3.html', mcp_servers=mcp_servers)

# 设置页面路由 - 为了处理模板中的链接，但实际重定向到Page3
@app.route('/setting')
def setting():
    return redirect(url_for('page3'))

# API路由 - 获取所有MCP服务器
@app.route('/api/mcp/servers', methods=['GET'])
def get_mcp_servers():
    return jsonify(mcp_servers)

# API路由 - 添加新MCP服务器
@app.route('/api/mcp/servers', methods=['POST'])
def add_mcp_server():
    data = request.json
    
    # 验证必要字段
    transport = data.get('transport', 'sse')
    if transport == 'stdio':
        if 'name' not in data or 'command' not in data:
            return jsonify({"error": "缺少必要字段: name 或 command"}), 400
    else:
        required_fields = ['name', 'ip']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"缺少必要字段: {field}"}), 400

    # 生成新ID (当前最大ID + 1)
    new_id = 1
    if mcp_servers:
        new_id = max(server['id'] for server in mcp_servers) + 1

    # 创建新服务器对象
    new_server = {
        "id": new_id,
        "name": data['name'],
        "status": "offline",
        "ip": data.get('ip', ''),
        "latency": "0ms",
        "connection_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "key": data.get('key', ''),  # 添加Key字段
        "transport": transport,
        "command": data.get('command', ''),
        "args": data.get('args', []),
        "cwd": data.get('cwd', ''),
        "env": data.get('env', {})
    }
    
    # 如果请求中包含 auto_connect 字段并且为 True，则尝试连接
    auto_connect = data.get('auto_connect', False)
    tools_list = []
    
    if auto_connect:
        try:
            # 尝试连接真实MCP服务器
            success, new_server, tools = connect_to_real_mcp(new_server)
            
            # 如果连接失败，仍然添加服务器，但状态为离线
            if not success:
                new_server['status'] = 'offline'
            else:
                # 处理工具列表，确保它是可序列化的
                if tools:
                    try:
                        # 尝试将工具对象转换为字典列表
                        for tool in tools:
                            if hasattr(tool, 'name'):
                                # 如果是对象，转换为字典
                                tool_name = str(getattr(tool, 'name', '未知'))
                                tool_dict = {
                                    'name': tool_name,
                                    'description': str(getattr(tool, 'description', '')),
                                    'enabled': get_tool_state(server_id, tool_name)
                                }
                                
                                # 处理 inputSchema
                                input_schema = getattr(tool, 'inputSchema', {})
                                if input_schema and isinstance(input_schema, dict):
                                    tool_dict['inputSchema'] = input_schema
                                else:
                                    tool_dict['inputSchema'] = {}
                                    
                                tools_list.append(tool_dict)
                            else:
                                # 如果是字典
                                if isinstance(tool, dict) and 'name' in tool:
                                    tool_name = str(tool.get('name', '未知'))
                                    tools_list.append({
                                        'name': tool_name,
                                        'description': str(tool.get('description', '')),
                                        'inputSchema': tool.get('inputSchema', {}),
                                        'enabled': get_tool_state(server_id, tool_name)
                                    })
                                else:
                                    # 其他情况，尝试转换为字符串
                                    tool_name = str(tool)
                                    tools_list.append({
                                        'name': tool_name, 
                                        'description': '',
                                        'enabled': get_tool_state(server_id, tool_name)
                                    })
                    except Exception as e:
                        util.log(1, f"工具列表序列化失败: {e}")
                        # 如果转换失败，只返回工具名称
                        tools_list = []
                        for tool in tools:
                            tool_name = str(tool)
                            tools_list.append({
                                'name': tool_name,
                                'enabled': get_tool_state(server_id, tool_name)
                            })
                
        except Exception as e:
            util.log(1, f"自动连接失败: {e}")
            new_server['status'] = 'offline'
    
    # 添加到服务器列表
    mcp_servers.append(new_server)
    save_mcp_servers(mcp_servers)
    
    # 返回新服务器信息
    return jsonify({
        "message": f"服务器 {new_server['name']} 已添加",
        "server": new_server,
        "tools": tools_list
    }), 201

# API路由 - 更新MCP服务器状态
@app.route('/api/mcp/servers/<int:server_id>/status', methods=['PUT'])
def update_server_status(server_id):
    data = request.json
    for server in mcp_servers:
        if server['id'] == server_id:
            server['status'] = data.get('status', server['status'])
            save_mcp_servers(mcp_servers)
            return jsonify(server)
    return jsonify({"error": "服务器未找到"}), 404

# API路由 - 重启MCP服务器
@app.route('/api/mcp/servers/<int:server_id>/restart', methods=['POST'])
def restart_server(server_id):
    for server in mcp_servers:
        if server['id'] == server_id:
            # 这里可以添加实际的重启逻辑
            server['status'] = 'online'
            server['connection_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_mcp_servers(mcp_servers)
            return jsonify({"message": f"服务器 {server['name']} 已重启", "server": server})
    return jsonify({"error": "服务器未找到"}), 404

# API路由 - 断开MCP服务器连接
@app.route('/api/mcp/servers/<int:server_id>/disconnect', methods=['POST'])
def disconnect_server(server_id):
    global mcp_servers, mcp_clients
    for server in mcp_servers:
        if server['id'] == server_id:
            # 这里可以添加实际的断开连接逻辑
            server['status'] = 'offline'
            
            # 删除客户端对象
            if server_id in mcp_clients:
                del mcp_clients[server_id]
                
            # 更新工具可用状态
            tool_registry.mark_all_unavailable(server_id)
            
            save_mcp_servers(mcp_servers)
            return jsonify({"message": f"服务器 {server['name']} 已断开连接", "server": server})
    return jsonify({"error": "服务器未找到"}), 404

# API路由 - 连接MCP服务器
@app.route('/api/mcp/servers/<int:server_id>/connect', methods=['POST'])
def connect_server(server_id):
    global mcp_servers
    for i, server in enumerate(mcp_servers):
        if server['id'] == server_id:
            try:
                # 尝试连接真实MCP服务器
                util.log(1, f"正在连接MCP服务器: {server['name']} ({server.get('ip', '')})")
                success, updated_server, _ = connect_to_real_mcp(server)

                # 更新服务器信息
                mcp_servers[i] = updated_server
                save_mcp_servers(mcp_servers)

                if success:
                    tools_list = tool_registry.get_server_tools(
                        server_id,
                        include_disabled=True,
                        include_unavailable=False,
                    )
                    util.log(1, f"MCP服务器连接成功: {updated_server['name']}，获取到 {len(tools_list)} 个工具")

                    return jsonify({
                        "message": f"服务器 {updated_server['name']} 已连接",
                        "server": updated_server,
                        "tools": tools_list,
                        "success": True
                    })
                else:
                    util.log(1, f"MCP服务器连接失败: {updated_server['name']}")
                    return jsonify({
                        "message": f"服务器 {updated_server['name']} 连接失败",
                        "server": updated_server,
                        "success": False
                    }), 500
            except Exception as e:
                return jsonify({
                    "message": f"服务器 {server['name']} 连接失败: {str(e)}",
                    "server": server,
                    "success": False
                }), 500
    return jsonify({"error": "服务器未找到"}), 404

# API路由 - 更新MCP服务器配置
@app.route('/api/mcp/servers/<int:server_id>', methods=['PUT'])
def update_mcp_server(server_id):
    """更新MCP服务器配置"""
    global mcp_servers, mcp_clients
    data = request.json
    auto_reconnect = data.get('auto_reconnect', False)

    # 查找服务器
    server = None
    server_index = None
    for i, s in enumerate(mcp_servers):
        if s['id'] == server_id:
            server = s
            server_index = i
            break

    if not server:
        return jsonify({"success": False, "message": "服务器未找到"}), 404

    # 更新基本信息
    server['name'] = data.get('name', server['name'])
    transport = data.get('transport', server.get('transport', 'sse'))
    server['transport'] = transport

    # 根据传输类型更新配置
    if transport == 'stdio':
        server['command'] = data.get('command', '')
        args_input = data.get('args', [])
        # 如果args是字符串，拆分为列表
        if isinstance(args_input, str):
            # 简单按空格拆分，支持引号
            import shlex
            try:
                server['args'] = shlex.split(args_input)
            except:
                # 如果shlex失败，简单按空格拆分
                server['args'] = args_input.split() if args_input else []
        else:
            server['args'] = args_input

        server['cwd'] = data.get('cwd', '')

        # 处理环境变量
        env_input = data.get('env', {})
        if isinstance(env_input, str):
            try:
                server['env'] = json.loads(env_input)
            except:
                util.log(1, f"环境变量JSON解析失败: {env_input}")
                server['env'] = {}
        else:
            server['env'] = env_input

        # 清空SSE相关字段
        server['ip'] = ''
        server['key'] = ''
    else:
        # SSE模式
        server['ip'] = data.get('ip', '')
        server['key'] = data.get('key', '')
        # 清空本地命令字段
        server['command'] = ''
        server['args'] = []
        server['cwd'] = ''
        server['env'] = {}

    # 保存配置
    save_mcp_servers(mcp_servers)

    # 如果需要自动重连
    if auto_reconnect:
        # 先断开
        if server_id in mcp_clients:
            try:
                del mcp_clients[server_id]
                tool_registry.mark_all_unavailable(server_id)
            except Exception as e:
                util.log(1, f"断开连接失败: {e}")

        # 重新连接
        try:
            success, updated_server, tools = connect_to_real_mcp(server)
            if success:
                # 更新服务器信息
                mcp_servers[server_index] = updated_server
                save_mcp_servers(mcp_servers)
                return jsonify({
                    "success": True,
                    "message": "配置已更新并重新连接",
                    "server": updated_server
                })
            else:
                return jsonify({
                    "success": True,
                    "message": "配置已更新，但重新连接失败",
                    "server": server
                })
        except Exception as e:
            util.log(1, f"重新连接失败: {e}")
            return jsonify({
                "success": True,
                "message": f"配置已更新，但重新连接失败: {str(e)}",
                "server": server
            })

    return jsonify({
        "success": True,
        "message": "配置已更新",
        "server": server
    })

# API路由 - 删除MCP服务器
@app.route('/api/mcp/servers/<int:server_id>', methods=['DELETE'])
def delete_server(server_id):
    global mcp_servers
    for i, server in enumerate(mcp_servers):
        if server['id'] == server_id:
            # 如果服务器处于连接状态，先断开连接
            if server['status'] == 'online':
                # 删除客户端对象
                if server_id in mcp_clients:
                    del mcp_clients[server_id]
                tool_registry.remove_server(server_id)

                # 更新服务器状态
                server['status'] = 'offline'
            
            # 删除服务器
            deleted_server = mcp_servers.pop(i)
            tool_registry.remove_server(server_id)
            save_mcp_servers(mcp_servers)
            return jsonify({"message": f"服务器 {deleted_server['name']} 已删除", "server": deleted_server})
    return jsonify({"error": "服务器未找到"}), 404

# API路由 - 调用MCP工具
@app.route('/api/mcp/servers/<int:server_id>/call', methods=['POST'])
def call_server_tool(server_id):
    data = request.json
    method = data.get('method')
    params = data.get('params', {})
    
    if not method:
        return jsonify({"error": "缺少方法名"}), 400
        
    success, result = call_mcp_tool(server_id, method, params)
    
    if success:
        # 处理结果，确保它是可序列化的
        try:
            # 尝试将结果转换为可序列化的格式
            if hasattr(result, '__dict__'):
                # 如果是对象，转换为字典
                result_dict = dict(vars(result))
                return jsonify({
                    "success": True,
                    "result": result_dict
                })
            else:
                # 如果已经是字典或其他可序列化对象
                return jsonify({
                    "success": True,
                    "result": result
                })
        except Exception as e:
            # 如果转换失败，返回字符串形式
            return jsonify({
                "success": True,
                "result": str(result)
            })
    else:
        return jsonify({
            "success": False,
            "error": result
        }), 500

# API路由 - 获取服务器工具列表
@app.route('/api/mcp/servers/<int:server_id>/tools', methods=['GET'])
def get_server_tools(server_id):
    for server in mcp_servers:
        if server['id'] == server_id:
            # 检查服务器是否在线
            if server['status'] != 'online':
                return jsonify({
                    "success": False,
                    "message": "服务器离线",
                    "tools": []
                })
            
            tools_list = tool_registry.get_server_tools(
                server_id,
                include_disabled=True,
                include_unavailable=False,
            )

            if not tools_list:
                client = get_mcp_client(server_id)
                if not client:
                    return jsonify({
                        "success": False,
                        "message": "未找到服务器连接",
                        "tools": []
                    })
                try:
                    client.list_tools(refresh=True)
                    tools_list = tool_registry.get_server_tools(
                        server_id,
                        include_disabled=True,
                        include_unavailable=False,
                    )
                except Exception as e:
                    return jsonify({
                        "success": False,
                        "message": f"获取工具列表失败: {str(e)}",
                        "tools": []
                    })

            return jsonify({
                "success": True,
                "message": "获取工具列表成功",
                "tools": tools_list
            })

    return jsonify({
        "success": False,
        "message": "服务器未找到",
        "tools": []
    }), 404

# API路由 - 获取所有在线服务器的工具列表
@app.route('/api/mcp/servers/online/tools', methods=['GET'])
def get_all_online_server_tools():
    global mcp_servers
    
    aggregated: Dict[str, Dict[str, Any]] = {}
    
    for server in mcp_servers:
        if server['status'] != 'online':
            continue
        server_id = server['id']
        tools = tool_registry.get_server_tools(
            server_id,
            include_disabled=True,
            include_unavailable=False,
        )
        if not tools:
            client = get_mcp_client(server_id)
            if client:
                try:
                    client.list_tools(refresh=True)
                    tools = tool_registry.get_server_tools(
                        server_id,
                        include_disabled=True,
                        include_unavailable=False,
                    )
                except Exception as e:
                    util.log(1, f"获取服务器 {server['name']} 工具列表失败: {e}")
                    tools = []
        for tool in tools:
            name = tool.get('name')
            if not name:
                continue
            current = aggregated.get(name)
            if not current or tool.get('last_checked', 0.0) >= current.get('last_checked', 0.0):
                aggregated[name] = tool
    
    unique_tools = sorted(aggregated.values(), key=lambda item: item['name'])
    
    return jsonify({
        "success": True,
        "message": "获取所有在线服务器工具列表成功",
        "tools": unique_tools
    })

# API路由 - 直接调用MCP工具（无需指定服务器ID）
@app.route('/api/mcp/tools/<string:tool_name>', methods=['POST'])
def call_mcp_tool_direct(tool_name):
    """
    直接调用MCP工具，自动选择在线服务器
    :param tool_name: 工具名称
    :return: 工具调用结果
    """
    global mcp_servers
    
    # 获取请求参数
    params = request.json or {}
    
    # 查找所有在线服务器
    online_servers = [server for server in mcp_servers if server['status'] == 'online']
    
    if not online_servers:
        return jsonify({
            "success": False,
            "error": "没有在线的MCP服务器"
        }), 404
    
    # 遍历在线服务器，尝试调用工具
    for server in online_servers:
        server_id = server['id']

        tools = tool_registry.get_server_tools(
            server_id,
            include_disabled=True,
            include_unavailable=False,
        )
        target_tool = next((tool for tool in tools if tool.get('name') == tool_name), None)

        if not target_tool:
            client = get_mcp_client(server_id)
            if not client:
                continue
            try:
                client.list_tools(refresh=True)
                tools = tool_registry.get_server_tools(
                    server_id,
                    include_disabled=True,
                    include_unavailable=False,
                )
                target_tool = next((tool for tool in tools if tool.get('name') == tool_name), None)
            except Exception as e:
                util.log(1, f"服务器 {server['name']} 获取工具列表失败: {e}")
                continue

        if not target_tool or not target_tool.get('enabled', True):
            continue

        # 调用工具
        success, result = call_mcp_tool(server_id, tool_name, params)

        if success:
            try:
                if hasattr(result, '__dict__'):
                    result_dict = dict(vars(result))
                    return jsonify({
                        "success": True,
                        "result": result_dict,
                        "server": server['name']
                    })
                return jsonify({
                    "success": True,
                    "result": result,
                    "server": server['name']
                })
            except Exception as e:
                return jsonify({
                    "success": True,
                    "result": str(result),
                    "server": server['name']
                })
        else:
            util.log(1, f"服务器 {server['name']} 调用工具 {tool_name} 失败: {result}")
            continue
    
    # 所有服务器都尝试过了，但都失败了
    return jsonify({
        "success": False,
        "error": f"没有找到支持 {tool_name} 工具的在线服务器，或者所有服务器调用都失败"
    }), 404

# 检查所有MCP客户端连接状态并自动重连
def check_mcp_connections():
    """
    定时检查所有MCP客户端连接状态，如果发现断线则自动重连
    """
    global mcp_servers, mcp_clients, connection_check_timer
    
    # util.log(1, "正在检查MCP客户端连接状态...")
    reconnected_servers = []
    
    for server in mcp_servers:
        server_id = server['id']
        
        # 检查服务器状态是否为在线
        if server['status'] == 'online':
            client = get_mcp_client(server_id)
            
            if client:
                # 尝试获取工具列表来测试连接状态
                try:
                    # 首先检查客户端的connected属性
                    if not client.connected:
                        util.log(1, f"服务器 {server['name']} (ID: {server_id}) 连接状态为断开，尝试重新连接...")
                        # 连接已断开，尝试重新连接
                        success, updated_server, tools = connect_to_real_mcp(server)
                        if success:
                            # 更新服务器信息
                            for i, s in enumerate(mcp_servers):
                                if s['id'] == server_id:
                                    mcp_servers[i] = updated_server
                                    reconnected_servers.append(updated_server['name'])
                                    break
                        continue
                    
                    # 尝试调用一个简单的工具来测试连接
                    test_success, test_result = client.call_tool("ping", {})
                    if not test_success:
                        # util.log(1, f"服务器 {server['name']} (ID: {server_id}) 测试调用失败，尝试重新连接...")
                        # 调用失败，可能已断开连接，尝试重新连接
                        success, updated_server, tools = connect_to_real_mcp(server)
                        if success:
                            # 更新服务器信息
                            for i, s in enumerate(mcp_servers):
                                if s['id'] == server_id:
                                    mcp_servers[i] = updated_server
                                    reconnected_servers.append(updated_server['name'])
                                    break
                        continue
                    
                    # 如果工具调用成功但工具列表为空，也尝试重新连接
                    tools = client.list_tools(refresh=True)
                    if not tools:
                        # util.log(1, f"服务器 {server['name']} (ID: {server_id}) 工具列表为空，尝试重新连接...")
                        # 连接可能有问题，尝试重新连接
                        success, updated_server, tools = connect_to_real_mcp(server)
                        if success:
                            # 更新服务器信息
                            for i, s in enumerate(mcp_servers):
                                if s['id'] == server_id:
                                    mcp_servers[i] = updated_server
                                    reconnected_servers.append(updated_server['name'])
                                    break
                except Exception as e:
                    # util.log(1, f"检查服务器 {server['name']} (ID: {server_id}) 连接状态时出错: {e}")
                    # 连接出错，标记为离线并尝试重新连接
                    server['status'] = 'offline'
                    success, updated_server, tools = connect_to_real_mcp(server)
                    if success:
                        # 更新服务器信息
                        for i, s in enumerate(mcp_servers):
                            if s['id'] == server_id:
                                mcp_servers[i] = updated_server
                                reconnected_servers.append(updated_server['name'])
                                break
    
    # if reconnected_servers:
    #     util.log(1, f"已自动重新连接以下服务器: {', '.join(reconnected_servers)}")
    
    # 安排下一次检查
    schedule_connection_check() 

# 安排连接检查定时任务
def schedule_connection_check():
    """
    安排下一次连接检查定时任务
    """
    global connection_check_timer
    
    # 取消现有定时器（如果有）
    if connection_check_timer:
        try:
            connection_check_timer.cancel()
        except:
            pass
    
    # 创建新的定时器
    connection_check_timer = threading.Timer(CONNECTION_CHECK_INTERVAL, check_mcp_connections)
    connection_check_timer.daemon = True  # 设置为守护线程，这样主程序退出时它会自动结束
    connection_check_timer.start()

# API路由 - 切换工具状态
@app.route('/api/mcp/servers/<int:server_id>/tools/<string:tool_name>/toggle', methods=['POST'])
def toggle_tool_state(server_id, tool_name):
    """
    切换工具的启用/禁用状态
    """
    try:
        # 获取请求数据
        data = request.json or {}
        enabled = data.get('enabled', True)
        
        # 验证服务器是否存在
        server = None
        for s in mcp_servers:
            if s['id'] == server_id:
                server = s
                break
        
        if not server:
            return jsonify({
                "success": False,
                "message": "服务器不存在"
            }), 404
        
        # 设置工具状态
        set_tool_state(server_id, tool_name, enabled)
        tool_registry.update_tool_enabled(server_id, tool_name, enabled)
        
        util.log(1, f"工具 {tool_name} 在服务器 {server['name']} 上已{'启用' if enabled else '禁用'}")
        
        updated_tools = tool_registry.get_server_tools(
            server_id,
            include_disabled=True,
            include_unavailable=False,
        )

        return jsonify({
            "success": True,
            "message": f"工具 {tool_name} 已{'启用' if enabled else '禁用'}",
            "tool_name": tool_name,
            "enabled": enabled,
            "tools": updated_tools
        })
        
    except Exception as e:
        util.log(1, f"切换工具状态失败: {e}")
        return jsonify({
            "success": False,
            "message": f"切换工具状态失败: {str(e)}"
        }), 500

# 启动连接检查
def start_connection_check():
    """
    启动MCP连接检查定时任务
    """
    util.log(1, "启动MCP连接状态检查定时任务...")
    schedule_connection_check()

# 主程序入口
def run():
    # 禁止服务器日志输出的类
    class NullLogHandler:
        def write(self, *args, **kwargs):
            pass
    
    # 使用gevent的pywsgi服务器，并禁用日志输出
    from gevent import pywsgi
    server = pywsgi.WSGIServer(
        ('0.0.0.0', 5010), 
        app,
        log=NullLogHandler()
    )
    server.serve_forever()

# 启动MCP服务器
def start():
    # 启动连接检查定时任务
    # start_connection_check() TODO 暂时取消定时检查任务
    
    # 输出启动信息
    util.log(1, "MCP服务已启动在端口5010")
    
    # 启动服务器
    from scheduler.thread_manager import MyThread
    MyThread(target=run).start()

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.DEBUG)
    app.logger.setLevel(logging.DEBUG)
    logging.getLogger('werkzeug').setLevel(logging.DEBUG)
    app.run(host='0.0.0.0', port=5010, debug=True)
