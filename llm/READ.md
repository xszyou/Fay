1、利用vllm部署大模型，加速大模型生成速度
conda create -n vllm python=3.9 -y
conda activate vllm

# Install vLLM with CUDA 12.1.
pip install vllm

安装flash attention2
conda install -c nvidia cuda-nvcc
pip install -U flash-attn==2.5.8


2、部署启动
下载大模型到任意文件目录，如：/mnt/f/xuniren/aimodels/ChatGLM3/THUDM/chatglm3-6b
质谱chatglm启动命令：
CUDA_VISIBLE_DEVICES=0 python -m vllm.entrypoints.openai.api_server \
--model="/mnt/f/xuniren/aimodels/ChatGLM3/THUDM/chatglm3-6b" \
--max-model-len=1024 \
--trust-remote-code \
--tensor-parallel-size=1 \
--port=8101 \
--served-model-name THUDM/chatglm3-6b

测试
curl http://127.0.0.1:8101/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "THUDM/chatglm3-6b",
        "prompt": "北京天气怎么样2",
        "max_tokens": 768,
        "temperature": 0
    }'
 
curl http://127.0.0.1:8101/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
    "model": "THUDM/chatglm3-6b",
    "max_tokens": 768,
    "temperature": 0,
    "messages": [
    {"role": "system", "content": "你是一个助理"},
    {"role": "user", "content": "北京天气咋样"}
    ]
    }'
    
同义前文部署
CUDA_VISIBLE_DEVICES=0 python -m vllm.entrypoints.openai.api_server \
--model="/mnt/f/xuniren/aimodels/qwen-int4" \
--max-model-len=1024 \
--tensor-parallel-size=1 \
--trust-remote-code \
--port=8101 \
--served-model-name Qwen/Qwen-int4 

测试
curl http://127.0.0.1:8101/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "Qwen/Qwen-int4",
        "prompt": "北京天气怎么样2",
        "max_tokens": 768,
        "temperature": 0
    }'
 
 llama3-chinese部署
 CUDA_VISIBLE_DEVICES=0 python -m vllm.entrypoints.openai.api_server \
--model="/root/aimodels/Llama-Chinese/model/Atom-7B-Chat" \
--max-model-len=1024 \
--tensor-parallel-size=1 \
--trust-remote-code \
--port=8101 \
--served-model-name llama3/Atom-7B-Chat 

测试
curl http://127.0.0.1:8101/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "llama3/Atom-7B-Chat",
        "prompt": "北京天气怎么样2",
        "max_tokens": 768,
        "temperature": 0
    }'

----------------------------------------------------------------------------------------------------------------------
二、采用fastchat部署大模型，降低显存占用，vllm会吃掉24g现存，而fastchat则用16g显存（测试基准chatglm3-6b或者qwen-1.5-7b模型）
1、安装fastchat
conda create -n fastchat python=3.10
conda activate fastchat

git clone https://github.com/lm-sys/FastChat
cd Fastchat

pip3 install -e ".[model_worker,webui]"

安装flash attention
git clone https://github.com/Dao-AILab/flash-attention
cd flash-attention
conda install -c nvidia cuda-nvcc # 为了使用conda内的cuda环境安装 flash_attn
pip install flash_attn
cd csrc/layer_norm && pip install .

2、测试
命令行测试
python -m fastchat.serve.cli --model-path /mnt/f/xuniren/aimodels/ChatGLM-6B/Qwen-7B-Chat/
类似openai接口测试
第一步是启动控制器服务，启动命令如下所示：
python -m fastchat.serve.controller --host 0.0.0.0
第二步是启动 Model Worker 服务，启动命令如下所示
启动不带推理加速的 模型worker
python -m fastchat.serve.model_worker --model-path /mnt/f/xuniren/aimodels/ChatGLM-6B/Qwen-7B-Chat --host 0.0.0.0 --port 8101
python -m fastchat.serve.model_worker --model-path /mnt/f/xuniren/aimodels/ChatGLM-6B/Qwen-7B-Chat/ --host 0.0.0.0 --port 8101 --dtype=half
启动 带vllm推理加速的 模型worker
python -m fastchat.serve.vllm_worker --model-path Qwen1.5-7B-Chat --host 0.0.0.0 --dtype=half  
#第三步是启动 RESTFul API 服务，启动命令如下所示：
python -m fastchat.serve.openai_api_server --host 0.0.0.0
第四步
python -m fastchat.serve.gradio_web_server --host 0.0.0.0


curl http://127.0.0.1:8101/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "Qwen-7B-Chat",
        "prompt": "北京天气怎么样2",
        "max_tokens": 768,
        "temperature": 0
    }'

3、使用
正式使用我采用提供了openai一样的接口的服务
conda activate fastchat
python -m fastchat.serve.controller --host 0.0.0.0
python -m fastchat.serve.model_worker --model-path /mnt/f/xuniren/aimodels/ChatGLM-6B/Qwen-7B-Chat --load-8bit
python -m fastchat.serve.openai_api_server --host 0.0.0.0 --port 8101

修改fay项目下system.conf文件下的模型名称为Qwen-7B-Chat，即
gpt_base_url=http://127.0.0.1:8101/v1
gpt_model_engine=Qwen-7B-Chat

启动fay：python app.py