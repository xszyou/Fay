#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
    ngrok.cc 内网穿透服务 Python 版
    本程序仅适用于ngrok.cc 使用前请先在 https://ngrok.cc 注册账号.
    Linux 系统一般自带Python 可以直接运行
    赋予权限 chmod 755 sunny.py
    感谢 hauntek 提供的 python-ngrok 原版程序
    本程序仅供学习交流使用,请勿用于非法用途.
    
    Edit by xszyou in 2023-01-31:
    1、整体代码重构，便于外部程序调用;
    2、修复若干bug;
    3、支持ngrok服务器重连及本地端口重连。


"""
import socket
import ssl
import json
import struct
import random
import sys
import time
import threading

from utils import util

class NgrokCilent(object):

    def __init__(self, clientId):
        self.__running = False
        self.clientId = clientId
        self.host = None # Ngrok服务器地址
        self.port = None # 端口
        self.tunnels = list() # 渠道队列
        self.reqIdaddr = dict()
        self.localaddr = dict()
        self.bufsize = 1024 # 吞吐量
        self.mainsocket = None # 主控socket
        self.localSocket = None # 本地socket
        self.remoteSocket = None # 远程socket
        self.ClientId = ''
        self.pingtime = 0

    

    # ngrok.cc 获取服务器设置
    def update_server_config(self):
        host = 'www.ngrok.cc'
        port = 443
        
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ssl_client = ssl.wrap_socket(client, ssl_version=ssl.PROTOCOL_TLSv1_2) # ssl.PROTOCOL_TLSv1_2
            ssl_client.connect((host, port))
        except Exception:
            util.log(1, 'ngrok连接认证服务器: https://www.ngrok.cc 错误.')
            time.sleep(10)
            sys.exit()

        header = "POST " + "/api/clientid/clientid/%s" + " HTTP/1.1" + "\r\n"
        header += "Content-Type: text/html" + "\r\n"
        header += "Host: %s" + "\r\n"
        header += "\r\n"
        buf = header % (self.clientId, host)
        ssl_client.sendall(buf.encode('utf-8')) # 发送请求头

        fd = ssl_client.makefile('rb', 0)
        body = bytes()
        while True:
            line = fd.readline().decode('utf-8')
            if line == "\n" or line == "\r\n":
                chunk_size = int(fd.readline(), 16)
                if chunk_size > 0:
                    body = fd.read(chunk_size).decode('utf-8')
                    break

        ssl_client.close()

        authData = json.loads(body)
        if authData['status'] != 200:
            util.log(1, 'ngrok认证错误:%s, ErrorCode:%s' % (authData['msg'], authData['status']))
            time.sleep(10)
            sys.exit()

        util.log(1, 'ngrok认证成功,正在连接服务器...')
        # 设置映射隧道,支持多渠道[客户端id]
        self.ngrok_adds(authData['data'])
        proto = authData['server'].split(':')
        self.host = str(proto[0]) # Ngrok服务器地址
        self.port = int(proto[1]) # 端口
        return

    # ngrok.cc 添加到渠道队列
    def ngrok_adds(self, Tunnel):
        for tunnelinfo in Tunnel:
            if tunnelinfo.get('proto'):
                if tunnelinfo.get('proto').get('http'):
                    protocol = 'http'
                if tunnelinfo.get('proto').get('https'):
                    protocol = 'https'
                if tunnelinfo.get('proto').get('tcp'):
                    protocol = 'tcp'

                proto = tunnelinfo['proto'][protocol].split(':') # 127.0.0.1:80 拆分成数组
                if proto[0] == '':
                    proto[0] = '127.0.0.1'
                if proto[1] == '' or proto[1] == 0:
                    proto[1] = 80

                body = dict()
                body['protocol'] = protocol
                body['hostname'] = tunnelinfo['hostname']
                body['subdomain'] = tunnelinfo['subdomain']
                body['httpauth'] = tunnelinfo['httpauth']
                body['rport'] = tunnelinfo['remoteport']
                body['lhost'] = str(proto[0])
                body['lport'] = int(proto[1])
                self.tunnels.append(body) # 加入渠道队列

    #获取ping包
    def get_ping_json(self):
            Payload = dict()
            body = dict()
            body['Type'] = 'Ping'
            body['Payload'] = Payload
            buffer = json.dumps(body)
            return(buffer)
    
    #ssl socket 连接
    def connect_remote(self, host, port):
        try:
            host = socket.gethostbyname(host)
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ssl_client = ssl.wrap_socket(client, ssl_version=ssl.PROTOCOL_SSLv23)
            ssl_client.connect((host, port))
            ssl_client.setblocking(1)
        except socket.error:
            return None
        return ssl_client

    #发送包
    def send_pack(self, sock, msg, isblock = False):
            if isblock:
                sock.setblocking(1)
            sock.sendall(struct.pack('<LL', len(msg), 0)+ msg.encode('utf-8'))
            if isblock:
                sock.setblocking(0)
    
    #获取本地ip，用于检测是否断网
    def dnsopen(self, host):
        try:
            ip = socket.gethostbyname(host)
        except socket.error:
            return None

        return ip

    #获取认证包
    def ngrok_auth_package(self):
            Payload = dict()
            Payload['ClientId'] = ''
            Payload['OS'] = 'darwin'
            Payload['Arch'] = 'amd64'
            Payload['Version'] = '2'
            Payload['MmVersion'] = '2.1'
            Payload['User'] = 'user'
            Payload['Password'] = ''
            body = dict()
            body['Type'] = 'Auth'
            body['Payload'] = Payload
            buffer = json.dumps(body)
            return(buffer)

    #获取注册包
    def ngrok_reg_proxy_package(self, ClientId):
            Payload = dict()
            Payload['ClientId'] = ClientId
            body = dict()
            body['Type'] = 'RegProxy'
            body['Payload'] = Payload
            buffer = json.dumps(body)
            return(buffer)

    #socket发送
    def send_buf(self, sock, buf, isblock = False):
            if isblock:
                sock.setblocking(1)
            sock.sendall(buf)
            if isblock:
                sock.setblocking(0)
    #计算包长度
    def tolen(self, v):
            if len(v) == 8:
                return struct.unpack('<II', v)[0]
            return 0

    #获取随机字符串
    def rand_char(self, length):
        _chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghijklmnopqrstuvwxyz"
        return ''.join(random.sample(_chars, length))

    #请求隧道
    def req_tunnel(self, ReqId, Protocol, Hostname, Subdomain, HttpAuth, RemotePort):
            Payload = dict()
            Payload['ReqId'] = ReqId
            Payload['Protocol'] = Protocol
            Payload['Hostname'] = Hostname
            Payload['Subdomain'] = Subdomain
            Payload['HttpAuth'] = HttpAuth
            Payload['RemotePort'] = RemotePort
            body = dict()
            body['Type'] = 'ReqTunnel'
            body['Payload'] = Payload
            buffer = json.dumps(body)
            return(buffer)

    #连接到本地应用
    def connect_local(self, localhost, localport):
            try:
                localhost = socket.gethostbyname(localhost)
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client.connect((localhost, localport))
                client.setblocking(1)
            except socket.error:
                return False

            return client
    
    # 客户端程序处理过程
    # linkstate 0:未连接 1:已连接ngrok服务器，2：已经连接到本地应用 #
    # type 1:连接ngrok服务器 2:启动控制：注册、认证、启动隧道 3:启动代理
    def HKClient(self, sock, linkstate, type,  tosock = None):
        recvbuf = bytes()
        while self.__running:
            try:
                if linkstate == 0:
                    if type == 1: #ngrok服务器的连接
                        self.send_pack(sock, self.ngrok_auth_package(), False)
                        linkstate = 1
                    if type == 2:#启动控制：注册、认证、启动隧道
                        self.send_pack(sock, self.ngrok_reg_proxy_package(self.ClientId), False)
                        linkstate = 1
                    if type == 3:#启动代理
                        linkstate = 1

                recvbut = sock.recv(self.bufsize)
                if not recvbut: break

                if len(recvbut) > 0:
                    if not recvbuf:
                        recvbuf = recvbut
                    else:
                        recvbuf += recvbut

                if type == 1 or (type == 2 and linkstate == 1):
                    lenbyte = self.tolen(recvbuf[0:8])
                    if len(recvbuf) >= (8 + lenbyte):
                        buf = recvbuf[8:lenbyte + 8].decode('utf-8')
                        js = json.loads(buf)
                        if type == 1:
                            if js['Type'] == 'ReqProxy':
                                self.remoteSocket = self.connect_remote(self.host, self.port)
                                if self.remoteSocket:
                                    thread = threading.Thread(target = self.HKClient, args = (self.remoteSocket, 0, 2))#远程客户端已经连接，监测本地应用连接
                                    thread.setDaemon(True)
                                    thread.start()
                            if js['Type'] == 'AuthResp':
                                self.ClientId = js['Payload']['ClientId']
                                self.send_pack(sock, self.get_ping_json())
                                self.pingtime = time.time()
                                for info in self.tunnels:
                                    reqid = self.rand_char(8)
                                    self.send_pack(sock, self.req_tunnel(reqid, info['protocol'], info['hostname'], info['subdomain'], info['httpauth'], info['rport']))
                                    self.reqIdaddr[reqid] = (info['lhost'], info['lport'])
                            if js['Type'] == 'NewTunnel':
                                if js['Payload']['Error'] != '':
                                    util.log(1, 'ngrok隧道建立失败: %s' % js['Payload']['Error'])
                                    time.sleep(30)
                                else:
                                    util.log(1, 'ngrok隧道建立成功: %s' % js['Payload']['Url']) # 注册成功
                                    self.localaddr[js['Payload']['Url']] = self.reqIdaddr[js['Payload']['ReqId']]
                        if type == 2:
                            if js['Type'] == 'StartProxy':
                                localhost, localport = self.localaddr[js['Payload']['Url']]

                                self.localSocket = self.connect_local(localhost, localport)
                                if self.localSocket: #本地应用连接成功
                                    thread = threading.Thread(target = self.HKClient, args = (self.localSocket, 0, 3, sock))#本地应用已经连接，启用数据转发
                                    thread.setDaemon(True)
                                    thread.start()
                                    tosock = self.localSocket
                                    linkstate = 2
                                else:
                                    body = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Web服务错误</title><meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no"><meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1"><style>html,body{height:100%%}body{margin:0;padding:0;width:100%%;display:table;font-weight:100;font-family:"Microsoft YaHei",Arial,Helvetica,sans-serif}.container{text-align:center;display:table-cell;vertical-align:middle}.content{border:1px solid #ebccd1;text-align:center;display:inline-block;background-color:#f2dede;color:#a94442;padding:30px}.title{font-size:18px}.copyright{margin-top:30px;text-align:right;color:#000}</style></head><body><div class="container"><div class="content"><div class="title">隧道 %s 无效<br>无法连接到<strong>%s</strong>. 此端口尚未提供Web服务</div></div></div></body></html>'
                                    html = body % (js['Payload']['Url'], localhost + ':' + str(localport))
                                    header = "HTTP/1.0 502 Bad Gateway" + "\r\n"
                                    header += "Content-Type: text/html" + "\r\n"
                                    header += "Content-Length: %d" + "\r\n"
                                    header += "\r\n" + "%s"
                                    buf = header % (len(html.encode('utf-8')), html)
                                    self.send_buf(sock, buf.encode('utf-8'))

                        if len(recvbuf) == (8 + lenbyte):
                            recvbuf = bytes()
                        else:
                            recvbuf = recvbuf[8 + lenbyte:]

                if type == 3 or (type == 2 and linkstate == 2):
                    self.send_buf(tosock, recvbuf)
                    recvbuf = bytes()

            except socket.error:
                break

        if type == 1:
            self.mainsocket = None
        if type == 3:
            try:
                tosock.shutdown(socket.SHUT_WR)
            except socket.error:
                tosock.close()

        sock.close()

    def start(self):
        self.__running = True
        self.update_server_config()
        while self.__running:
            try:
                # 检测控制连接是否已经连接.
                if self.mainsocket is None:
                    ip = self.dnsopen(self.host)
                    if ip is None:
                        util.log(1, 'ngrok隧道网络连接失败.')
                        time.sleep(10)
                        continue
                    self.mainsocket = self.connect_remote(ip, self.port)
                    if self.mainsocket is None:
                        util.log(1, 'ngrok隧道服务器连接失败.')
                        time.sleep(10)
                        continue
                    thread = threading.Thread(target = self.HKClient, args = (self.mainsocket, 0, 1))#主控制连接，监测远程客户端连接
                    thread.setDaemon(True)
                    thread.start()

                # 发送心跳
                if self.pingtime + 20 < time.time() and self.pingtime != 0:
                    self.send_pack(self.mainsocket, self.get_ping_json())
                    self.pingtime = time.time()

                time.sleep(1)

            except socket.error as e:
                self.pingtime = 0
            except KeyboardInterrupt:
                sys.exit()
    #停止
    def stop(self):
        util.log(1, 'ngrok隧道正在关闭...')
        self.__running = False
        if self.mainsocket:
            self.mainsocket.close()
            self.mainsocket = None
        if self.remoteSocket:
            self.remoteSocket.close()
            self.remoteSocket = None
        if self.localSocket:
            self.localSocket.close()
            self.localSocket = None
        self.pingtime = 0
        

#test
if __name__ == '__main__':
    ngrok = NgrokCilent("21364129xxxx")
    ngrok.start()


