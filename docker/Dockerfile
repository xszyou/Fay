FROM docker.m.daocloud.io/python:3.10

COPY install_deps.sh /usr/local/bin/install_deps.sh
RUN chmod +x /usr/local/bin/install_deps.sh && /usr/local/bin/install_deps.sh
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple/
COPY requirements.txt /app/
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt
COPY ./ /app
CMD ["python", "main.py"]
