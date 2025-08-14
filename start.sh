# 先備份, 再部署, 再比對差異
docker-compose up --build nacos-backup && docker-compose up --build config-setup && sleep 2 && docker-compose up --build nacos-diff