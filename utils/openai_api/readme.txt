
1、vllm启动chatglm

conda create -n vllm python=3.10
conda install pytorch==2.1.0 torchvision==0.16.0 torchaudio==2.1.0 pytorch-cuda=12.1 -c pytorch -c nvidia

启动
python -m vllm.entrypoints.openai.api_server --tensor-parallel-size=1  --trust-remote-code --max-model-len 1024 --model THUDM/chatglm3-6b

python -m vllm.entrypoints.openai.api_server --host 127.0.0.1 --port 8101 --tensor-parallel-size=1  --trust-remote-code --max-model-len 1024 --model THUDM/chatglm3-6b

测试
curl http://127.0.0.1:8101/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "THUDM/chatglm3-6b",
        "prompt": "请用20字内回复我,你今年多大了",
        "max_tokens": 20,
        "temperature": 0
    }'

多轮对话
curl -X POST "http://127.0.0.1:8101/v1/completions" \
-H "Content-Type: application/json" \
-d "{\"model\": \"THUDM/chatglm3-6b\",\"prompt\": \"你叫什么名字\", \"history\": [{\"role\": \"user\", \"content\": \"你出生在哪里.\"}, {\"role\": \"assistant\", \"content\": \"出生在北京\"}]}"


多轮对话
curl -X POST "http://127.0.0.1:8101/v1/chat/completions" \
-H "Content-Type: application/json" \
-d "{\"model\": \"THUDM/chatglm3-6b\", \"messages\": [{\"role\": \"system\", \"content\": \"You are ChatGLM3, a large language model trained by Zhipu.AI. Follow the user's instructions carefully. Respond using markdown.\"}, {\"role\": \"user\", \"content\": \"你好，给我讲一个故事，大概100字\"}], \"stream\": false, \"max_tokens\": 100, \"temperature\": 0.8, \"top_p\": 0.8}"
