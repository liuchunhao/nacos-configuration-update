import os
import sys
import json
import requests

from dotenv import load_dotenv

# 先嘗試載入 .env 檔案（如果有的話） override: False  # 不覆蓋已存在的環境變數
load_dotenv(dotenv_path=".env", override=False)

def main():
    """
    從環境變數讀取 GitLab CI/CD 的資訊，並發送一個格式化的通知到 Discord。
    """
    # 1. 從環境變數讀取必要的資訊
    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')

    # 2. 在 CI template 中定義的變數
    message_content = os.environ.get('DISCORD_MESSAGE_CONTENT', '')
    embed_color = int(os.environ.get('DISCORD_EMBED_COLOR', 0))

    project_name = os.environ.get('CI_PROJECT_NAME', 'N/A')
    pipeline_url = os.environ.get('CI_PIPELINE_URL', 'https://gitlab.com')
    branch_name = os.environ.get('CI_COMMIT_REF_NAME', 'N/A')

    commit_sha_short = os.environ.get('CI_COMMIT_SHORT_SHA', 'N/A')
    commit_sha_full = os.environ.get('CI_COMMIT_SHA', '')
    project_url = os.environ.get('CI_PROJECT_URL', '')
    commit_author = os.environ.get('CI_COMMIT_AUTHOR', 'N/A')
    pipeline_timestamp = os.environ.get('CI_PIPELINE_CREATED_AT', '')

    # 2. 檢查最重要的 Webhook URL 是否存在
    if not webhook_url:
        print("ERROR: DISCORD_WEBHOOK_URL environment variable is not set or is empty.", file=sys.stderr)
        sys.exit(1)

    # 3. 組合 Commit 的連結
    commit_url = f"{project_url}/-/commit/{commit_sha_full}"

    # 4. 構造要發送到 Discord 的 JSON payload
    payload = {
        "content": message_content,
        "embeds": [{
            "title": project_name,
            "description": (
                f"分支 **{branch_name}** 的 Pipeline 狀態更新。\n\n"
                f"[**--> 點此查看 Pipeline**]({pipeline_url})\n"
                f"[**--> 點此查看 Commit 內容**]({commit_url})"
            ),
            "url": pipeline_url,
            "color": embed_color,
            "fields": [
                {
                    "name": "Commit",
                    "value": f"[{commit_sha_short}]({commit_url})",
                },
                {
                    "name": "Author",
                    "value": commit_author,
                }
            ],
            "footer": {
                "text": "GitLab CI/CD"
            },
            "timestamp": pipeline_timestamp
        }]
    }

    # 5. 發送 HTTP POST 請求
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10
        )
        # 檢查是否有 HTTP 錯誤 (例如 4xx 或 5xx)
        response.raise_for_status()
        print("Successfully sent notification to Discord.")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to send notification to Discord: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
