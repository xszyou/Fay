##  语音服务介绍

该服务以modelscope funasr语音识别为基础


## Install
pip install torch
pip install modelscope
pip install testresources
pip install websockets
pip install torchaudio
pip install FunASR

## Start server

2、python -u ASR_server.py --host "0.0.0.0" --port 10197 --ngpu 0 

## Fay connect
更改fay/system.conf配置项，并重新启动fay.

https://www.bilibili.com/video/BV1qs4y1g74e/?share_source=copy_web&vd_source=64cd9062f5046acba398177b62bea9ad


## Acknowledge
感谢
1. 中科大脑算法工程师张聪聪
2.  [cgisky1980](https://github.com/cgisky1980/FunASR) 
3. [modelscope](https://github.com/modelscope/modelscope)
4. [FunASR](https://github.com/alibaba-damo-academy/FunASR)
5. [Fay数字人助理](https://github.com/TheRamU/Fay).

--------------------------------------------------------------------------------------
