FROM docker.m.daocloud.io/python:3.12
#FROM python:3.12 --->  Nick
COPY app /app
RUN chmod +x /app/docker/install_deps.sh \
#    && mv /app/docker/sources.list /etc/apt/sources.list \   ---> 添加对应的sources list可以提升apt install 效率
    && /app/docker/install_deps.sh \
    && pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple/ \
    && pip install --no-cache-dir -r /app/docker/requirements.txt
WORKDIR /app
CMD ["python", "main.py"]

