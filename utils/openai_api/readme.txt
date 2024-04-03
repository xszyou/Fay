
1、vllm启动chatglm
python -m vllm.entrypoints.openai.api_server --tensor-parallel-size=1  --trust-remote-code --max-model-len 1024 --model THUDM/chatglm3-6b