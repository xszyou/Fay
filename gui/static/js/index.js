// fayApp.js
class FayInterface {
  constructor(baseWsUrl, baseApiUrl, vueInstance) {
    this.baseWsUrl = baseWsUrl;
    this.baseApiUrl = baseApiUrl;
    this.websocket = null;
    this.vueInstance = vueInstance; 
  }

  connectWebSocket() {
    if (this.websocket) {
      this.websocket.onopen = null;
      this.websocket.onmessage = null;
      this.websocket.onclose = null;
      this.websocket.onerror = null;
    }

    this.websocket = new WebSocket(this.baseWsUrl);

    this.websocket.onopen = () => {
      console.log('WebSocket connection opened');
    };

    this.websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleIncomingMessage(data);
    };

    this.websocket.onclose = () => {
      console.log('WebSocket connection closed. Attempting to reconnect...');
      setTimeout(() => this.connectWebSocket(), 5000); 
    };

    this.websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  async fetchData(url, options = {}) {
    try {
      // Ensure headers are properly set for POST requests
      if (options.method === 'POST') {
        options.headers = {
          'Content-Type': 'application/json',
          ...options.headers
        };
      }
      
      const response = await fetch(url, options);
      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      const data = await response.json();
      return data;
    } catch (error) {
      console.error('Error fetching data:', error);
      throw error; // Rethrow to handle in the calling function
    }
  }

  getVoiceList() {
    return this.fetchData(`${this.baseApiUrl}/api/get-voice-list`);
  }

  getAudioDeviceList() {
    return this.fetchData(`${this.baseApiUrl}/api/get-audio-device-list`);
  }

  submitConfig(config) {
    return this.fetchData(`${this.baseApiUrl}/api/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config })
    });
  }

  controlEyes(state) {
    return this.fetchData(`${this.baseApiUrl}/api/control-eyes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state })
    });
  }

  startLive() {
    return this.fetchData(`${this.baseApiUrl}/api/start-live`, {
      method: 'POST'
    });
  }

  stopLive() {
    return this.fetchData(`${this.baseApiUrl}/api/stop-live`, {
      method: 'POST'
    });
  }

  getRunStatus() {
    return this.fetchData(`${this.baseApiUrl}/api/get-run-status`, {
      method: 'POST'
    });
  }

  getMessageHistory(username) {
    return new Promise((resolve, reject) => {
      const url = `${this.baseApiUrl}/api/get-msg`;
      const xhr = new XMLHttpRequest();
      xhr.open("POST", url);
      xhr.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
      const send_data = `data=${encodeURIComponent(JSON.stringify({ username }))}`;
      xhr.send(send_data);

      xhr.onreadystatechange = function () {
        if (xhr.readyState === 4) {
          if (xhr.status === 200) {
            try {
              const data = JSON.parse(xhr.responseText);
              if (data && data.list) {
                const combinedList = data.list.flat(); 
                resolve(combinedList);
              } else {
                resolve([]);
              }
            } catch (e) {
              console.error('Error parsing response:', e);
              reject(e);
            }
          } else {
            reject(new Error(`Request failed with status ${xhr.status}`));
          }
        }
      };
    });
  }

  getUserList() {
    return this.fetchData(`${this.baseApiUrl}/api/get-member-list`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
  }

  getData() {
    return this.fetchData(`${this.baseApiUrl}/api/get-data`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
}

  getTime(){
    const date = new Date();
    const year = date.getFullYear();
    const month = (date.getMonth() + 1).toString().padStart(2, '0'); // 月份从0开始，需要+1
    const day = date.getDate().toString().padStart(2, '0');
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const seconds = date.getSeconds().toString().padStart(2, '0');
    const milliseconds = date.getMilliseconds().toString().padStart(3, '0');
    const currentDateTimeWithMs = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}.${milliseconds}`;
    return currentDateTimeWithMs
  }

  handleIncomingMessage(data) {
    const vueInstance = this.vueInstance; 
  //   console.log('Incoming message:', data);
    if (data.liveState !== undefined) {
      vueInstance.liveState = data.liveState;
      if (data.liveState === 1) {
        vueInstance.configEditable = false;
      } else if (data.liveState === 0) {
        vueInstance.configEditable = true;
      }
    }

    if (data.voiceList !== undefined) {
      vueInstance.voiceList = data.voiceList.map(voice => ({
        value: voice.id,
        label: voice.name
      }));
    }

    if (data.deviceList !== undefined) {
      vueInstance.deviceList = data.deviceList.map(device => ({
        value: device,
        label: device
      }));
    }

    if (data.panelMsg !== undefined) {
      vueInstance.panelMsg = data.panelMsg; 
    
    }
    if (data.robot) {
      console.log(data.robot)
      vueInstance.$set(vueInstance, 'robot', data.robot); 
      }
    if (data.panelReply !== undefined) {
      console.log('收到消息:', data.panelReply);
      vueInstance.panelReply = data.panelReply.content;
      
      // 更新用户列表
      const userExists = vueInstance.userList.some(user => user[1] === data.panelReply.username);
      if (!userExists) {
        vueInstance.userList.push([data.panelReply.uid, data.panelReply.username]);
      }

      if (vueInstance.selectedUser && data.panelReply.username === vueInstance.selectedUser[1]) {
        // 查找是否已存在相同content_id的消息
        const existingMessageIndex = vueInstance.messages.findIndex(
          msg => msg.id === data.panelReply.id && msg.type === data.panelReply.type
        );
        
        if (existingMessageIndex !== -1) {
          // 更新现有消息（拼接内容）
          const existingMessage = vueInstance.messages[existingMessageIndex];
          // 拼接新内容到现有内容
          existingMessage.content = existingMessage.content + data.panelReply.content;
          existingMessage.timetext = this.getTime();

          // 检测 think 标签状态
          const hasThinkStart = existingMessage.content.includes('<think>');
          const hasThinkEnd = existingMessage.content.includes('</think>');
          if (hasThinkStart && !hasThinkEnd) {
            // think 正在接收中，展开并显示加载状态
            vueInstance.$set(existingMessage, 'thinkExpanded', true);
            vueInstance.$set(existingMessage, 'thinkLoading', true);
          } else if (hasThinkStart && hasThinkEnd) {
            // think 接收完成，关闭加载状态
            vueInstance.$set(existingMessage, 'thinkLoading', false);
          }

          // 强制更新视图
          vueInstance.$forceUpdate();
        } else {
          // 添加新消息
          const newMessage = {
            id: data.panelReply.id,
            username: data.panelReply.username,
            content: data.panelReply.content,
            type: data.panelReply.type,
            timetext: this.getTime(),
            is_adopted: data.panelReply.is_adopted ? 1 : 0,
            thinkExpanded: false,
            thinkLoading: false
          };

          // 检测新消息是否包含 think 开始标签
          if (newMessage.content.includes('<think>') && !newMessage.content.includes('</think>')) {
            newMessage.thinkExpanded = true;
            newMessage.thinkLoading = true;
          }

          vueInstance.messages.push(newMessage);
        }

        // 滚动到底部
        vueInstance.$nextTick(() => {
          const chatContainer = vueInstance.$el.querySelector('.chatmessage');
          if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
          }
        });
      }
    }

    if (data.is_connect !== undefined) {
      vueInstance.isConnected = data.is_connect;
    }

    if (data.remote_audio_connect !== undefined) {
      vueInstance.remoteAudioConnected = data.remote_audio_connect;
    }
  }
}

new Vue({
  el: '#app',
  delimiters: ["[[", "]]"],
  data() {
    return {
      messages: [],
      newMessage: '',
      fayService: null,
      liveState: 0,
      isConnected: false,
      remoteAudioConnected: false,
      userList: [],
      selectedUser: null,
      loading: false,
      chatMessages: {},
      panelMsg: '', 
      panelReply: '', 
      robot:'static/images/Normal.gif',
      base_url: window.location.protocol + '//' + window.location.hostname + ':' + window.location.port,
      hostname: window.location.hostname,
      play_sound_enabled: false,
      source_record_enabled: false,
      userListTimer: null,
      thinkPanelExpanded: true,
      thinkContent: '',
      isThinkPanelMinimized: false,
      mcpOnlineStatus: false,
      mcpCheckTimer: null,
    };
  },
  watch: {
    // 消息列表变化时的监听（保留用于其他扩展）
  },
  created() {
    this.initFayService(); 
    this.getData();
    this.startUserListTimer();
    this.checkMcpStatus();
    this.startMcpStatusTimer();
  },
  methods: {
    initFayService() {
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsHost = window.location.hostname;
      const wsUrl = `${wsProtocol}//${wsHost}:10003`;
      this.fayService = new FayInterface(wsUrl, this.base_url, this);
      this.fayService.connectWebSocket();
      this.fayService.websocket.addEventListener('open', () => {
        this.loadUserList();
      });
    },
    async loadUserList() {
      try {
        const result = await this.fayService.getUserList();
        if (result && result.list) {
          this.userList = result.list;
          if (this.userList.length > 0) {
            this.selectedUser = this.userList[0];
            await this.loadMessageHistory(this.selectedUser[1]);
          }
        }
      } catch (error) {
        console.error('Failed to load user list:', error);
        this.$message.error('Failed to load user list. Please try again.');
      }
    },
    sendMessage() {
      let _this = this;
      let text = _this.newMessage;
      if (!text) {
        alert('请输入内容');
        return;
      }
      if (_this.selectedUser === 'others' && !_this.othersUser) {
        alert('请输入自定义用户名');
        return;
      }
      if (this.liveState != 1) {
        alert('请先开启服务');
        return;
      }
      let usernameToSend = _this.selectedUser === 'others' ? _this.othersUser : _this.selectedUser[1];

      this.timer = setTimeout(() => {
        let height = document.querySelector('.chatmessage').scrollHeight;
        document.querySelector('.chatmessage').scrollTop = height;
      }, 1000);
      _this.newMessage = '';
      let url = `${this.base_url}/api/send`;
      let send_data = {
        "msg": text,
        "username": usernameToSend
      };

      let xhr = new XMLHttpRequest();
      xhr.open("post", url);
      xhr.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
      xhr.send('data=' + encodeURIComponent(JSON.stringify(send_data)));
      let executed = false;
      xhr.onreadystatechange = async function () {
        if (!executed && xhr.status === 200) {
          executed = true;
        }
      };
    },
    getData() {
      this.fayService.getRunStatus().then((data) => {
          if (data) {
              if(data.status){
                  this.liveState = 1;
                  this.configEditable = false;
              }else{
                  this.liveState = 0;
                  this.configEditable = true;
              }
              
          }
      });
      this.fayService.getData().then((data) => {
          if (data) {
              this.updateConfigFromData(data.config);
          }
      });
  },
  updateConfigFromData(config) {
    
      if (config.interact) {
          this.play_sound_enabled = config.interact.playSound;
      }
      if (config.source && config.source.record) {
          this.source_record_enabled = config.source.record.enabled;
      }
  },
  saveConfig() {
    let url = `${this.base_url}/api/submit`;
    let send_data = {
        "config": {
            "source": {
                "record": {
                    "enabled": this.source_record_enabled,
                },
            },
            "interact": {
                "playSound": this.play_sound_enabled,
            }
        }
    };

    let xhr = new XMLHttpRequest()
    xhr.open("post", url)
    xhr.setRequestHeader("Content-type", "application/x-www-form-urlencoded")
    xhr.send('data=' + JSON.stringify(send_data))
    let executed = false
    xhr.onreadystatechange = async function () {
        if (!executed && xhr.status === 200) {
            try {
                let data = await eval('(' + xhr.responseText + ')')
                executed = true
            } catch (e) {
            }
        }
    }
},
  changeRecord(){
    if(this.source_record_enabled){
      this.source_record_enabled = false
    }else{
      this.source_record_enabled = true
    }
    this.saveConfig()
  },
  changeSound(){
    if(this.play_sound_enabled){
      this.play_sound_enabled = false
    }else{
      this.play_sound_enabled = true
    }
    this.saveConfig()
  },
    loadUserList() {
      this.fayService.getUserList().then((response) => {
        if (response && response.list) {
          if (response.list.length == 0){
            // 检查是否已经有默认用户
            const defaultUserExists = this.userList.some(user => user[1] === 'User');
            if (!defaultUserExists) {
              // 只有在不存在默认用户时才添加
              const info = [];
              info[0] = 1;
              info[1] = 'User';
              this.userList.push(info);
              this.selectUser(info);
              console.log('添加默认用户: User');
            }
          } else {
            this.userList = response.list;
            if (!this.selectedUser) {
              this.selectUser(this.userList[0]);
            }
          }
        }
      });
    },
    startUserListTimer() {
      // 清除可能存在的旧定时器
      if (this.userListTimer) {
        clearInterval(this.userListTimer);
      }
      // 设置新的定时器，每30秒执行一次
      this.userListTimer = setInterval(() => {
        this.loadUserList();
      }, 30000);
    },
    // 组件销毁时清除定时器
    beforeDestroy() {
      if (this.userListTimer) {
        clearInterval(this.userListTimer);
        this.userListTimer = null;
      }
      if (this.mcpCheckTimer) {
        clearInterval(this.mcpCheckTimer);
        this.mcpCheckTimer = null;
      }
    },
    selectUser(user) {
      this.selectedUser = user;
      this.fayService.websocket.send(JSON.stringify({ "Username": user[1] }));
      this.loadMessageHistory(user[1], 'common'); 
    },
    startLive() {
      this.liveState = 2
      this.fayService.startLive().then(() => {
        this.sendSuccessMsg('已开启！');
        this.getData();
      });
  },
  stopLive() {
      this.fayService.stopLive().then(() => {
          this.liveState = 3
          this.sendSuccessMsg('已关闭！');
      });
  },

    loadMessageHistory(username, type) {
      this.fayService.getMessageHistory(username).then((response) => {
        if (response) {
          this.messages = response;
          if(type == 'common'){
          this.$nextTick(() => {
            const chatContainer = document.querySelector('.chatmessage');
            if (chatContainer) {
              chatContainer.scrollTop = chatContainer.scrollHeight;
            }
          });
        }
        }
      });
    },
    sendSuccessMsg(message) {
      this.$notify({
          title: '成功',
          message,
          type: 'success',
      });
  
} ,
adoptText(id) {
// 调用采纳接口
this.fayService.fetchData(`${this.base_url}/api/adopt-msg`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ id })
})
.then((response) => {
  if (response && response.status === 'success') {
    // 处理成功的响应
    this.$notify({
      title: '成功',
      message: response.msg,  // 显示成功消息
      type: 'success',
    });
    
    this.loadMessageHistory(this.selectedUser[1], 'adopt');
  } else {
    // 处理失败的响应
    this.$notify({
      title: '失败',
      message: response ? response.msg : '请求失败',
      type: 'error',
    });
  }
})
.catch((error) => {
  // 处理网络错误或HTTP错误
  this.$notify({
    title: '错误',
    message: error.message || '请求失败',
    type: 'error',
  });
});
}
,
  minimizeThinkPanel() {
    this.isThinkPanelMinimized = !this.isThinkPanelMinimized;
    const panel = document.querySelector('.think-panel');
    panel.classList.toggle('minimized');
  },

  // 解析消息中的 think 内容
  parseThinkContent(content) {
    if (!content) {
      return { thinkContent: '', mainContent: '' };
    }

    // 先尝试匹配完整的 think 标签
    const completeRegex = /<think>([\s\S]*?)<\/think>/i;
    const completeMatch = content.match(completeRegex);

    if (completeMatch && completeMatch[1]) {
      // 完整的 think 标签
      const rawThink = completeMatch[1];
      const thinkContent = this.trimThinkLines(rawThink);
      const mainContent = content.replace(completeRegex, '').replace(/^\s+/, '').replace(/\s+$/, '');
      return { thinkContent, mainContent };
    }

    // 尝试匹配未完成的 think 标签（只有开始标签）
    const incompleteRegex = /<think>([\s\S]*)/i;
    const incompleteMatch = content.match(incompleteRegex);

    if (incompleteMatch && incompleteMatch[1]) {
      // 未完成的 think 标签，正在接收中
      const rawThink = incompleteMatch[1];
      const thinkContent = this.trimThinkLines(rawThink);
      const mainContent = ''; // 正在思考中，主内容为空
      return { thinkContent, mainContent };
    }

    return { thinkContent: '', mainContent: content.replace(/^\s+/, '').replace(/\s+$/, '') };
  },

  // 处理 think 内容的每行 trim
  trimThinkLines(rawThink) {
    const lines = rawThink.split(/\r?\n/);
    const trimmedLines = [];
    for (let i = 0; i < lines.length; i++) {
      const trimmed = lines[i].replace(/^\s+/, '').replace(/\s+$/, '');
      if (trimmed.length > 0) {
        trimmedLines.push(trimmed);
      }
    }
    return trimmedLines.join('\n');
  },

  // 切换 think 内容的展开/折叠状态
  toggleThink(index) {
    const message = this.messages[index];
    this.$set(message, 'thinkExpanded', !message.thinkExpanded);
  },
  
  // 检查MCP服务器状态
  checkMcpStatus() {
    const mcpUrl = `http://${this.hostname}:5010/api/mcp/servers`;
    
    // 使用超时设置的fetch请求
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000); // 3秒超时
    
    fetch(mcpUrl, { signal: controller.signal })
      .then(response => {
        clearTimeout(timeoutId);
        if (!response.ok) {
          throw new Error('MCP服务器响应不正常');
        }
        return response.json();
      })
      .then(data => {
        if (Array.isArray(data)) {
          // 检查是否有任何一个MCP服务器在线
          const hasOnlineServer = data.some(server => server.status === 'online');
          this.mcpOnlineStatus = hasOnlineServer;
        } else {
          console.warn('MCP服务器返回的数据格式不正确');
          this.mcpOnlineStatus = false;
        }
      })
      .catch(error => {
        clearTimeout(timeoutId);
        // 如果是超时错误，不输出详细错误信息
        if (error.name === 'AbortError') {
          console.warn('MCP服务器请求超时');
        } else {
          console.warn('检查MCP状态出错:', error.message);
        }
        this.mcpOnlineStatus = false;
      });
  },
  
  // 启动MCP状态检查定时器
  startMcpStatusTimer() {
    // 清除可能存在的旧定时器
    if (this.mcpCheckTimer) {
      clearInterval(this.mcpCheckTimer);
    }
    // 设置新的定时器，每30秒检查一次MCP状态
    this.mcpCheckTimer = setInterval(() => {
      this.checkMcpStatus();
    }, 30000);
  },
  

  }
});
