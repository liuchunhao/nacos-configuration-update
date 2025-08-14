# configs/Dockerfile
FROM python:3.9-slim

WORKDIR /app

# 安裝依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製腳本和配置文件
COPY nacos_setup.py .
COPY nacos_backup.py .
COPY nacos_diff.py .
COPY discord_notify.py .

# 設置執行權限
RUN chmod +x nacos_setup.py
RUN chmod +x nacos_backup.py
RUN chmod +x nacos_diff.py
RUN chmod +x discord_notify.py

# 設置默認命令
CMD ["python", "nacos_setup.py"]