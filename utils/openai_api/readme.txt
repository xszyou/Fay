
1、vllm启动chatglm

conda create -n vllm python=3.10
conda install pytorch==2.1.0 torchvision==0.16.0 torchaudio==2.1.0 pytorch-cuda=12.1 -c pytorch -c nvidia


python -m vllm.entrypoints.openai.api_server --tensor-parallel-size=1  --trust-remote-code --max-model-len 1024 --model THUDM/chatglm3-6b

python -m vllm.entrypoints.openai.api_server --host 127.0.0.1 --port 8101 --tensor-parallel-size=1  --trust-remote-code --max-model-len 1024 --model THUDM/chatglm3-6b