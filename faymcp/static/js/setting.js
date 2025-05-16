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

    getData() {
        return this.fetchData(`${this.baseApiUrl}/api/get-data`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        });
    }

    submitConfig(config) {
        return this.fetchData(`${this.baseApiUrl}/api/submit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ config }),
        });
    }

    startLive() {
        return this.fetchData(`${this.baseApiUrl}/api/start-live`, {
            method: 'POST',
        });
    }

    stopLive() {
        return this.fetchData(`${this.baseApiUrl}/api/stop-live`, {
            method: 'POST',
        });
    }

    getRunStatus() {
        return this.fetchData(`${this.baseApiUrl}/api/get-run-status`, {
          method: 'POST'
        });
      }
  

    handleIncomingMessage(data) {
        const vueInstance = this.vueInstance; 
        console.log('Incoming message:', data);
        if (data.liveState !== undefined) {
            vueInstance.liveState = data.liveState;
            if (data.liveState === 1) {
                vueInstance.configEditable = false;
            } else if (data.liveState === 0) {
                vueInstance.configEditable = true;
            }
        }

        if (data.voiceList !== undefined) {
            vueInstance.voiceList = data.voiceList.map((voice) => ({
                value: voice.id,
                label: voice.name,
            }));
        }
        if (data.robot) {
            console.log(data.robot);
            vueInstance.$set(vueInstance, 'robot', data.robot);
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
    delimiters: ['[[', ']]'],
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
            robot: 'images/emoji.png',
            configEditable: true,
            source_liveRoom_url: '',
            play_sound_enabled: false,
            visualization_detection_enabled: false,
            source_record_enabled: false,
            source_record_device: '',
            attribute_name: "",
            attribute_gender: "",
            attribute_age: "",
            attribute_birth: "",
            attribute_zodiac: "",
            attribute_constellation: "",
            attribute_job: "",
            attribute_additional: "", 
            attribute_contact: "",
            attribute_voice: "",
            attribute_position: "",
            attribute_goal: "",
            QnA:"",
            interact_perception_gift: 0,
            interact_perception_follow: 0,
            interact_perception_join: 0,
            interact_perception_chat: 0,
            interact_perception_indifferent: 0,
            interact_maxInteractTime: 15,
            voiceList: [],
            deviceList: [],
            wake_word_enabled:false,
            wake_word: '',
            loading: false,
            remote_audio_connect: false,
            wake_word_type: 'common',
            wake_word_type_options: [{
                value: 'common',
                label: '普通'
            }, {
                value: 'front',
                label: '前置词'
            }],
            automatic_player_status: false,
            automatic_player_url: "",
            host_url: window.location.protocol + '//' + window.location.hostname + ':' + window.location.port,
            memory_isolate_by_user: false,
        };
    },
    created() {
        this.initFayService();
        this.getData();
    },
    methods: {
        initFayService() {
            const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws';
            const wsHost = window.location.hostname;
            this.fayService = new FayInterface(`${wsProtocol}://${wsHost}:10003`, this.host_url, this);
            this.fayService.connectWebSocket();
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
                    this.voiceList =  data.voice_list.map((voice) => ({
                        value: voice.id,
                        label: voice.name,
                    }));
                    this.updateConfigFromData(data.config);
                }
            });
        },
        updateConfigFromData(config) {
          
            if (config.interact) {
                this.play_sound_enabled = config.interact.playSound;
                this.visualization_detection_enabled = config.interact.visualization;
                this.QnA = config.interact.QnA;
            }
            if (config.source && config.source.record) {
                this.source_record_enabled = config.source.record.enabled;
                this.source_record_device = config.source.record.device;
                this.wake_word = config.source.wake_word;
                this.wake_word_type = config.source.wake_word_type;
                this.wake_word_enabled = config.source.wake_word_enabled;
                this.automatic_player_status = config.source.automatic_player_status;
                this.automatic_player_url = config.source.automatic_player_url;

            }
            if (config.attribute) {
                this.attribute_name = config.attribute.name;
                this.attribute_gender = config.attribute.gender;
                this.attribute_age = config.attribute.age;
                this.attribute_name = config.attribute.name;
                this.attribute_gender = config.attribute.gender;
                this.attribute_birth = config.attribute.birth;
                this.attribute_zodiac = config.attribute.zodiac;
                this.attribute_constellation = config.attribute.constellation;
                this.attribute_job = config.attribute.job;
                this.attribute_additional = config.attribute.additional; 
                this.attribute_contact = config.attribute.contact;
                this.attribute_voice = config.attribute.voice;
                this.attribute_position = config.attribute.position || "客服"; 
                this.attribute_goal = config.attribute.goal || "解决问题"; 
            }
            if (config.interact.perception) {
                this.interact_perception_follow = config.interact.perception.follow;
            }
            if (config.memory) {
                this.memory_isolate_by_user = config.memory.isolate_by_user || false;
            }
        },
        saveConfig() {
            let url = `${this.host_url}/api/submit`;
            let send_data = {
                "config": {
                    "source": {
                        "liveRoom": {
                            "enabled": this.configEditable,
                            "url": this.source_liveRoom_url
                        },
                        "record": {
                            "enabled": this.source_record_enabled,
                            "device": this.source_record_device
                        },
                        "wake_word_enabled": this.wake_word_enabled,
                        "wake_word": this.wake_word,
                        "wake_word_type": this.wake_word_type,
                        "automatic_player_status": this.automatic_player_status,
                        "automatic_player_url": this.automatic_player_url
                    },
                    "attribute": {
                        "voice": this.attribute_voice,
                        "name": this.attribute_name,
                        "gender": this.attribute_gender,
                        "age": this.attribute_age,
                        "birth": this.attribute_birth,
                        "zodiac": this.attribute_zodiac,
                        "constellation": this.attribute_constellation,
                        "job": this.attribute_job,
                        "additional": this.attribute_additional, 
                        "contact": this.attribute_contact,
                        "position": this.attribute_position, 
                        "goal": this.attribute_goal, 
                    },
                    "interact": {
                        "playSound": this.play_sound_enabled,
                        "visualization": this.visualization_detection_enabled,
                        "QnA": this.QnA,
                        "perception": {
                            "follow": this.interact_perception_follow
                        },
                        "maxInteractTime": this.interact_maxInteractTime
                    },
                    "memory": {
                        "isolate_by_user": this.memory_isolate_by_user
                    },
                    "items": []
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
                        console.log("data: " + data['result'])
                        executed = true
                    } catch (e) {
                    }
                }
            }
            this.sendSuccessMsg("配置已保存！");
        },
        startLive() {
            this.liveState = 2
            this.fayService.startLive().then(() => {
                this.configEditable = false;
                this.sendSuccessMsg('已开启！');
            });
        },
        stopLive() {
            this.liveState = 3
            this.fayService.stopLive().then(() => {
                this.configEditable = true;
                this.sendSuccessMsg('已关闭！');
            });
        },
        sendSuccessMsg(message) {
            this.$notify({
                title: '成功',
                message,
                type: 'success',
            });
        },
        clearMemory() {
            this.$confirm('清除记忆操作将删除Fay的所有对话记忆，清除后需要重启应用才能生效，确认继续吗?', '提示', {
                confirmButtonText: '确定',
                cancelButtonText: '取消',
                type: 'warning'
            }).then(() => {
                // 发送清除记忆请求
                fetch(`${this.host_url}/api/clear-memory`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        this.sendSuccessMsg(data.message || "记忆已清除，请重启应用使更改生效");
                    } else {
                        this.$notify({
                            title: '错误',
                            message: data.message || '清除记忆失败',
                            type: 'error'
                        });
                    }
                })
                .catch(error => {
                    this.$notify({
                        title: '错误',
                        message: '清除记忆请求失败',
                        type: 'error'
                    });
                });
            }).catch(() => {
                // 用户取消操作
            });
        },
        clonePersonality() {
            if (this.liveState === 1) {
                this.$prompt('请输入克隆要求', '克隆人格', {
                    confirmButtonText: '确定',
                    cancelButtonText: '取消',
                    inputPlaceholder: '请输入克隆要求，例如：你现在是一个活泼开朗的助手...'
                }).then(({ value }) => {
                    if (!value) {
                        this.$notify({
                            title: '提示',
                            message: '克隆要求不能为空',
                            type: 'warning'
                        });
                        return;
                    }
                    
                    // 直接启动genagents_flask.py并打开decision_interview.html页面
                    fetch(`${this.host_url}/api/start-genagents`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ instruction: value })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            // 弹出提示，显示克隆地址，不自动打开
                            this.$alert(`决策分析页面已启动，请复制以下链接在新窗口中打开：<br><br><code style="background-color: #f5f5f5; padding: 5px; border-radius: 3px;">${data.url}</code>`, '克隆人格', {
                                confirmButtonText: '确定',
                                dangerouslyUseHTMLString: true
                            });
                        } else {
                            this.$notify({
                                title: '错误',
                                message: data.message || '启动决策分析页面失败',
                                type: 'error'
                            });
                        }
                    })
                    .catch(error => {
                        this.$notify({
                            title: '错误',
                            message: '启动决策分析页面请求失败',
                            type: 'error'
                        });
                    });
                });
            } else {
                this.$notify({
                    title: '提示',
                    message: '请先开Fay后再执行此操作',
                    type: 'warning'
                });
            }
        },
    },
});
