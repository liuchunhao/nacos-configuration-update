import os
import sys

import requests
import json
import logging
import shutil
import time

from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NACOS_SERVER = os.getenv('NACOS_SERVER_ADDR', 'localhost:8848')
NACOS_USERNAME = os.getenv('NACOS_USERNAME', 'nacos')
NACOS_PASSWORD = os.getenv('NACOS_PASSWORD', 'nacos')
NACOS_AUTH_ENABLED = os.getenv('NACOS_AUTH_ENABLED', 'false').lower() == 'true'
# BACKUP_DIR = os.getenv('NACOS_BACKUP_DIR', 'export')
BACKUP_DIR = 'export'

BASE_URL = f"http://{NACOS_SERVER}"
NAMESPACE_API = f"{BASE_URL}/nacos/v1/console/namespaces"
CONFIGS_API = f"{BASE_URL}/nacos/v1/cs/configs"
LOGIN_API = f"{BASE_URL}/nacos/v1/auth/login"


def get_token():
    resp = requests.post(LOGIN_API, data={
        "username": NACOS_USERNAME,
        "password": NACOS_PASSWORD
    })
    resp.raise_for_status()
    try:
        return resp.json().get("accessToken")
    except Exception:
        return resp.text.strip()


def get_namespaces(headers):
    resp = requests.get(NAMESPACE_API, headers=headers)
    resp.raise_for_status()
    return resp.json().get("data", [])


def get_config_list(namespace, headers, page_no=1, page_size=100):
    params = {
        "tenant": namespace,
        "dataId": "",
        "group": "",
        "pageNo": page_no,
        "pageSize": page_size,
        "search": "accurate"
    }
    if namespace:
        params["tenant"] = namespace
    logger.info(f"Getting config list for namespace {namespace}, params: {params}, headers: {headers}")
    resp = requests.get(CONFIGS_API, params=params, headers=headers)
    resp.raise_for_status()
    return resp.json()


def get_config_content(data_id, group, namespace, headers):
    params = {
        "dataId": data_id,
        "group": group,
        "tenant": namespace
    }
    logger.info(f"Getting config content for {data_id}, params: {params}, headers: {headers}")
    resp = requests.get(CONFIGS_API, params=params, headers=headers)
    resp.raise_for_status()
    return resp.text


def safe_remove_directory(directory, max_retries=3, retry_delay=1):
    """Safely remove a directory with retries."""
    for attempt in range(max_retries):
        try:
            if os.path.exists(directory):
                shutil.rmtree(directory)
            return True
        except OSError as e:
            if attempt < max_retries - 1:
                logging.warning(f"Failed to remove {directory} (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(retry_delay)
            else:
                logging.error(f"Failed to remove {directory} after {max_retries} attempts: {e}")
                return False


def main():
    headers = {}
    if NACOS_AUTH_ENABLED:
        token = get_token()
        headers = {"Authorization": f"Bearer {token}"}
        logger.info(f"Login successful, got token: {token}")

    # Clean up old backup directory
    if not safe_remove_directory(BACKUP_DIR):
        logging.error("Failed to clean up old backup directory. Continuing anyway...")

    Path(BACKUP_DIR).mkdir(exist_ok=True)
    namespaces = get_namespaces(headers)
    logger.info(f"Found {len(namespaces)} namespaces.")

    for ns in namespaces:
        ns_id = ns.get("namespace", "")
        ns_name = ns.get("namespaceShowName", ns_id)
        ns_dir = Path(BACKUP_DIR) / (ns_name or "public")
        ns_dir.mkdir(exist_ok=True)
        logger.info(f"Backing up namespace: {ns_name} ({ns_id})")

        # 分頁獲取所有配置
        page_no = 1
        while True:
            try:
                configs_page = get_config_list(ns_id, headers, page_no=page_no)
            except requests.HTTPError as e:
                logger.error(f"Error backing up namespace {ns_name} ({ns_id}): {e}")
                sys.exit(1)

            configs = configs_page.get("pageItems", [])
            if not configs:
                break
            for cfg in configs:
                data_id = cfg["dataId"]
                group = cfg["group"]
                typ = cfg.get("type", "text")
                content = cfg.get("content", "")
                # 以 group 為子目錄
                group_dir = ns_dir / group
                group_dir.mkdir(exist_ok=True)
                # 以 dataId 為檔名
                file_path = group_dir / data_id
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.info(f"  - {group}/{data_id} ({typ})")
            # 是否還有下一頁
            if configs_page.get("pagesAvailable", 1) > page_no:
                page_no += 1
            else:
                break

    print(f"Backup finished! All configs saved in {BACKUP_DIR}/")


if __name__ == "__main__":
    main()