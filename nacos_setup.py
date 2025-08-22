# -*- coding: utf-8 -*-
#!/usr/bin/env python3
import os
import json
import requests
from pathlib import Path
from typing import Optional, Dict, Any
import logging
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

# Import the Discord Notifier class
# from discord_notify import DiscordNotifier

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NacosConfigLoader:
    def __init__(self):
        # 從環境變數獲取配置
        self.nacos_server = os.getenv('NACOS_SERVER_ADDR', 'localhost:8848')
        self.username = os.getenv('NACOS_USERNAME', 'nacos')
        self.password = os.getenv('NACOS_PASSWORD', 'nacos')
        self.auth_enabled = os.getenv('NACOS_AUTH_ENABLED', 'false').lower() == 'true'
        
        # 構建 API URL
        self.base_url = f"http://{self.nacos_server}"
        self.config_url = f"{self.base_url}/nacos/v1/cs/configs"
        self.login_url = f"{self.base_url}/nacos/v1/auth/login"
        
        # 初始化認證信息
        self.access_token = None
        self.auth_header = None
        
        # 如果啟用了認證，先登入
        if self.auth_enabled:
            self._login()

    def _login(self) -> None:
        """登入 Nacos 並獲取 access token"""
        try:
            logger.info("Nacos authentication enabled. Logging in...")
            logger.info(f"NACOS_SERVER_ADDR: {self.nacos_server}")
            logger.info(f"NACOS_USERNAME: {self.username}")
            logger.info(f"NACOS_PASSWORD: {self.password}")

            response = requests.post(
                self.login_url,
                data={
                    "username": self.username,
                    "password": self.password
                }
            )
            response.raise_for_status()
            
            # 嘗試解析 JSON 響應
            try:
                token_data = response.json()
                self.access_token = token_data.get('accessToken')
            except json.JSONDecodeError:
                # 如果不是 JSON，直接使用響應內容作為 token
                self.access_token = response.text.strip()
            
            if not self.access_token or self.access_token == "null":
                raise ValueError(f"Failed to get accessToken. Response was: {response.text}")
            
            logger.info("Login successful. AccessToken obtained.")
            self.auth_header = {"Authorization": f"Bearer {self.access_token}"}
            logger.info(f"ACCESS_TOKEN: {self.access_token}")
            
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            raise

    def create_namespace(self, namespace_name: str, namespace_desc: str = "") -> bool:
        """
        創建 Nacos 命名空間
        
        Args:
            namespace_name: 命名空間名稱
            namespace_desc: 命名空間描述
            
        Returns:
            bool: 是否創建成功
        """
        try:
            # 構建創建命名空間的 URL
            create_namespace_url = f"{self.base_url}/nacos/v1/console/namespaces"
            
            # 準備請求參數
            params = {
                "customNamespaceId": namespace_name,
                "namespaceName": namespace_name,
                "namespaceDesc": namespace_desc
            }
            
            # 發送請求
            headers = self.auth_header if self.auth_enabled else {}
            response = requests.post(
                create_namespace_url,
                params=params,
                headers=headers
            )
            response.raise_for_status()
            
            # 檢查響應
            if response.text.strip() == "true":
                logger.info(f"Successfully created namespace: {namespace_name}")
                return True
            else:
                logger.error(f"Failed to create namespace: {namespace_name}. Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating namespace: {str(e)}")
            return False

    def ensure_namespace_exists(self, namespace_name: str) -> bool:
        """
        確保命名空間存在，如果不存在則創建
        
        Args:
            namespace_name: 命名空間名稱
            
        Returns:
            bool: 命名空間是否存在或創建成功
        """
        try:
            # 構建查詢命名空間的 URL
            list_namespaces_url = f"{self.base_url}/nacos/v1/console/namespaces"
            
            # 發送請求
            headers = self.auth_header if self.auth_enabled else {}
            response = requests.get(
                list_namespaces_url,
                headers=headers
            )
            response.raise_for_status()
            
            # 解析響應
            namespaces = response.json()
            
            # 檢查命名空間是否存在
            for namespace in namespaces.get("data", []):
                if namespace.get("namespace") == namespace_name:
                    logger.info(f"Namespace {namespace_name} already exists")
                    return True
            
            # 如果命名空間不存在，創建它
            logger.info(f"Namespace {namespace_name} does not exist, creating...")
            return self.create_namespace(namespace_name)
            
        except Exception as e:
            logger.error(f"Error checking/creating namespace: {str(e)}")
            return False

    def publish_config(self, 
                      namespace_id: Optional[str], 
                      data_id: str, 
                      group: str, 
                      content_type: str, 
                      file_path: str) -> bool:
        """
        發布配置到 Nacos
        
        Args:
            namespace_id: 命名空間 ID，如果為 None 則使用默認命名空間
            data_id: 配置 ID
            group: 配置組
            content_type: 配置類型 (properties, yaml, json, text, xml)
            file_path: 配置文件路徑
            
        Returns:
            bool: 是否發布成功
        """
        try:
            # 如果指定了命名空間，確保它存在
            if namespace_id and not self.ensure_namespace_exists(namespace_id):
                logger.error(f"Failed to ensure namespace exists: {namespace_id}")
                return False
            
            # 讀取配置文件內容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if content_type in ["yml", "yaml"]:
                content_type = "yaml"
            elif content_type == "json":
                content_type = "json"
            elif content_type == "properties":
                content_type = "properties"

            logger.info(f"Publishing to Namespace: '{namespace_id}', Group: '{group}', DataID: '{data_id}', Type: '{content_type}'")
            
            # 準備請求參數
            params = {
                "dataId": data_id,
                "group": group,
                "type": content_type,
                "content": content
            }
            
            if namespace_id:
                params["tenant"] = namespace_id
            
            # 發送請求
            headers = self.auth_header if self.auth_enabled else {}
            response = requests.post(
                self.config_url,
                data=params,
                headers=headers
            )
            response.raise_for_status()
            
            # 檢查響應
            if response.text.strip() in ['true', 'ok']:
                logger.info(f"Successfully published: Namespace='{namespace_id}', Group='{group}', DataID='{data_id}'")
                return True
            else:
                logger.error(f"Failed to publish: Namespace='{namespace_id}', Group='{group}', DataID='{data_id}'. Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error publishing config: {str(e)}")
            return False

def main():
    # 創建配置加載器實例
    loader = NacosConfigLoader()
    
    # 掃描 import 目錄
    import_dir = Path("import")
    if not import_dir.exists():
        logger.warning("Import directory not found. Creating empty directory structure...")
        import_dir.mkdir(parents=True, exist_ok=True)
        return

    # 遍歷所有配置文件
    for namespace_dir in import_dir.iterdir():
        if not namespace_dir.is_dir():
            continue
            
        namespace = namespace_dir.name
        logger.info(f"Namespace: {namespace}")

        # 如果命名空間是 public，則跳過處理
        if namespace == "public":
            logger.info(f"Ignoring public namespace: {namespace}")
            continue

        # 確保命名空間存在
        if not loader.ensure_namespace_exists(namespace):
            logger.warn(f"Failed to ensure namespace exists: {namespace}")
            continue
        
        for group_dir in namespace_dir.iterdir():
            if not group_dir.is_dir():
                continue
                
            group = group_dir.name
            logger.info(f"Group: {group}")
            
            for file_path in group_dir.iterdir():
                if not file_path.is_file():
                    continue
                    
                logger.info(f"Processing file: {file_path}")
                
                # 獲取 data_id 和 content_type
                data_id = file_path.name
                content_type = file_path.suffix[1:]  # 移除點號
                
                logger.info(f"Data ID: {data_id}")
                logger.info(f"Content type: {content_type}")
                
                # 發布配置
                loader.publish_config(namespace, data_id, group, content_type, str(file_path))

    logger.info("All configurations processing finished.")

    # # 發送 Discord 成功通知 (如果 webhook URL 已設置)
    # webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    # if webhook_url:
    #     logger.info("Sending success notification to Discord...")
    #     notifier = DiscordNotifier(webhook_url)
    #     message_content = "Nacos 配置成功發布"
    #     notification_title = "Nacos 配置更新"
    #     utc_now = datetime.utcnow()
    #     utc_plus_8 = utc_now + timedelta(hours=8)
    #     # 這裡可以根據需要添加更多詳細信息到 fields
    #     success = notifier.send_message(
    #         content=message_content,
    #         title=notification_title,
    #         color=0x00ff00, # 綠色表示成功
    #         fields=[
    #             {
    #                 "name": "時間",
    #                 "value": utc_plus_8.strftime("%Y-%m-%d %H:%M:%S"),
    #                 "inline": True
    #             }
    #             # 可以在這裡添加更多 fields, 例如處理的配置文件數量等
    #         ]
    #     )
    #     if not success:
    #         logger.error("Failed to send Discord success notification.")
    # else:
    #     logger.warning("DISCORD_WEBHOOK_URL not set. Skipping Discord notification.")

if __name__ == "__main__":
    main()