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