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
        const response = await fetch(url, options);
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        return await response.json();
      } catch (error) {
        console.error('Error fetching data:', error);
        return null;
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
      return this.fetchData(`${this.baseApiUrl}/api/get_run_status`, {
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
        vueInstance.panelReply = data.panelReply.content; 
        const userExists = vueInstance.userList.some(user => user[1] === data.panelReply.username);
        if (!userExists) {
          vueInstance.userList.push([data.panelReply.uid, data.panelReply.username]);
        }
        if (vueInstance.selectedUser && data.panelReply.username === vueInstance.selectedUser[1]) {
          vueInstance.messages.push({
            username: data.panelReply.username,
            content: data.panelReply.content,
            type: data.panelReply.type,
            timetext: this.getTime(),
            is_adopted:0
          });
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
        base_url: 'http://127.0.0.1:5000'
      };
    },
    created() {
      this.initFayService();
      // this.loadUserList();
    },
    methods: {
      initFayService() {
        this.fayService = new FayInterface('ws://127.0.0.1:10003', this.base_url, this);
        this.fayService.connectWebSocket();
        this.fayService.websocket.addEventListener('open', () => {
          this.loadUserList();
      });
      this.fayService.getRunStatus().then((data) => {
        if (data) {
            if(data.status){
                this.liveState = 1;
            }else{
                this.liveState = 0;
            }
            
        }
    });
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
      loadUserList() {
        this.fayService.getUserList().then((response) => {
          if (response && response.list) {
            if (response.list.length == 0){
              info = [];
              info[0] = 1;
              info[1] = 'User';
              this.userList.push(info)
              this.selectUser(info);
            }else{
            this.userList = response.list;
            this.selectUser(this.userList[0]);
          }
        }
        });
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
              const chatContainer = this.$el.querySelector('.chatmessage');
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
  this.fayService.fetchData(`${this.base_url}/api/adopt_msg`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ id })  // 发送采纳请求
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

},
    }
  });
  