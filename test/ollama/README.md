1、在[ollama官网下载](https://ollama.com/download)安装ollama到本地或者服务器上

2、拉取常见模型(多选一)
```
ollama pull llama2:latest  #meta开源模型

ollama pull phi:latest  #微软开源模型

ollama pull gemma:latest #google开源模型

ollama pull yi:latest #01开源模型

ollama pull qwen:latest #阿里开源模型
```

3、修改系统配置文件system.conf 

本地配置
```
chat_module=ollama_api

ollama_ip =  127.0.0.1 
ollama_model =  phi:latest # llama2:latest , yi:lastest , pi:latest ,  gemma:latest  (开源大语言模型多选1)
```
服务配置
```
chat_module=ollama_api

ollama_ip = xxx.xxx.xxx.xxx  #服务器IP地址
ollama_model =  phi:latest # llama2:latest , yi:lastest , pi:latest ,  gemma:latest  (开源大语言模型多选1多选1)
```

4、启动ollama服务  
```
python main.py
```

备注：ollama接口由亿嘉和具身智能算法工程师陈张提供