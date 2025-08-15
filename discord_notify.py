# -*- coding: utf-8 -*-
#!/usr/bin/env python3
import os
import sys
import json
import requests
from typing import Optional, Dict, Any
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file.
# Existing environment variables will not be overwritten.
load_dotenv()

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DiscordNotifier:
    def __init__(self, webhook_url: str):
        """
        初始化 Discord 通知器
        
        Args:
            webhook_url: Discord webhook URL
        """
        self.webhook_url = webhook_url

    def send_message(self, 
                    content: str, 
                    title: Optional[str] = None,
                    color: int = 0x00ff00,  # 默認綠色
                    fields: Optional[list] = None) -> bool:
        """
        發送消息到 Discord
        
        Args:
            content: 消息內容
            title: 嵌入標題
            color: 嵌入顏色 (十六進制)
            fields: 額外的字段列表，每個字段是一個字典，包含 name 和 value
            
        Returns:
            bool: 是否發送成功
        """
        try:
            # 構建嵌入消息
            embed = {
                "description": content,
                "color": color,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if title:
                embed["title"] = title
                
            if fields:
                embed["fields"] = fields

            # 構建完整的 payload
            payload = {
                "embeds": [embed]
            }

            # 發送請求
            response = requests.post(
                self.webhook_url,
                json=payload
            )
            response.raise_for_status()
            
            logger.info("Successfully sent message to Discord")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message to Discord: {str(e)}")
            return False

def main():
    # 從環境變數獲取 webhook URL
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        logger.error("DISCORD_WEBHOOK_URL environment variable is not set")
        sys.exit(0)

    # 創建通知器實例
    notifier = DiscordNotifier(webhook_url)

    # 示例：發送一個簡單的消息
    if len(sys.argv) > 1:
        # 如果有命令行參數，使用第一個參數作為消息內容
        message = sys.argv[1]
        status = sys.argv[2] if len(sys.argv) > 2 else "success"
    else:
        # 否則使用默認消息
        message = "一個測試消息"
        status = "success"

    # 根據狀態設置顏色和狀態文本
    if status.lower() == "failure":
        color = 0xff0000  # 紅色
        status_text = "失敗"
    else:
        color = 0x00ff00  # 綠色
        status_text = "成功"

    # 從環境變數獲取 GitLab CI/CD 相關資訊
    gitlab_user = os.getenv('GITLAB_USER_NAME', 'N/A')
    project_url = os.getenv('CI_PROJECT_URL', 'N/A')
    pipeline_url = os.getenv('CI_PIPELINE_URL', 'N/A')

    # 構建要發送到 Discord 的字段
    fields = [
        {"name": "發布者", "value": gitlab_user, "inline": True},
        {"name": "GitLab Repo", "value": f"[異動檢查]({project_url})", "inline": True},
        {"name": "Pipeline", "value": f"[批准]({pipeline_url})", "inline": True},
    ]

    utc_now = datetime.utcnow()
    utc_plus_8 = utc_now + timedelta(hours=8)
    success = notifier.send_message(
        content=f"""{message}\n\n時間: {utc_plus_8.strftime("%Y-%m-%d %H:%M:%S")}\n\n狀態: {status_text}""",
        title="Nacos配置異動通知(待批准)",
        color=color,
        fields=fields
    )

    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main() 