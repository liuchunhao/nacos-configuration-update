import os
from pathlib import Path
import shutil
import logging
import requests
import json
from dotenv import load_dotenv

# Load environment variables from .env file.
# Existing environment variables will not be overwritten.
load_dotenv()

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NACOS_SERVER = os.getenv('NACOS_SERVER_ADDR', 'localhost:8848')
NACOS_USERNAME = os.getenv('NACOS_USERNAME', 'nacos')
NACOS_PASSWORD = os.getenv('NACOS_PASSWORD', 'nacos')
NACOS_AUTH_ENABLED = os.getenv('NACOS_AUTH_ENABLED', 'false').lower() == 'true'

# Control deletion logic
NACOS_DELETE_EXPORT_ONLY = os.getenv('NACOS_DELETE_EXPORT_ONLY', 'false').lower() == 'true'

# Control import synchronization logic
NACOS_SYNC_IMPORT = os.getenv('NACOS_SYNC_IMPORT', 'false').lower() == 'true'

BASE_URL = f"http://{NACOS_SERVER}"
NAMESPACE_API = f"{BASE_URL}/nacos/v1/console/namespaces"
CONFIGS_API = f"{BASE_URL}/nacos/v1/cs/configs"
LOGIN_API = f"{BASE_URL}/nacos/v1/auth/login"

def get_token():
    if not NACOS_AUTH_ENABLED:
        return None
    resp = requests.post(LOGIN_API, data={
        "username": NACOS_USERNAME,
        "password": NACOS_PASSWORD
    })
    resp.raise_for_status()
    try:
        return resp.json().get("accessToken")
    except Exception:
        return resp.text.strip()

def get_nacos_headers():
    headers = {}
    if NACOS_AUTH_ENABLED:
        token = get_token()
        if token:
             headers = {"Authorization": f"Bearer {token}"}
    return headers

def get_nacos_config_list(namespace, headers, page_no=1, page_size=100):
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
    logger.info(f"Getting config list from Nacos for namespace {namespace}")
    resp = requests.get(CONFIGS_API, params=params, headers=headers)
    resp.raise_for_status()
    return resp.json()

def delete_nacos_config(data_id, group, namespace, headers):
    params = {
        "dataId": data_id,
        "group": group,
        "tenant": namespace
    }
    logger.info(f"Deleting config from Nacos: {namespace}/{group}/{data_id}")
    resp = requests.delete(CONFIGS_API, params=params, headers=headers)
    resp.raise_for_status()
    return resp.text

def delete_nacos_namespace(namespace_id, headers):
    params = {
        "namespaceId": namespace_id
    }
    logger.info(f"Deleting namespace from Nacos: {namespace_id}")
    resp = requests.delete(NAMESPACE_API, params=params, headers=headers)
    resp.raise_for_status()
    return resp.text

def publish_nacos_config(data_id, group, namespace, content, headers):
    params = {
        "dataId": data_id,
        "group": group,
        "tenant": namespace,
        "content": content,
        "type": "text" # Assuming text type for simplicity, could enhance later
    }
    logger.info(f"Publishing/updating config in Nacos: {namespace}/{group}/{data_id}")
    # Use POST for publishing/updating (upsert behavior)
    resp = requests.post(CONFIGS_API, data=params, headers=headers)
    resp.raise_for_status() # Raise an exception for bad status codes
    return resp.text

def get_namespaces(headers):
    resp = requests.get(NAMESPACE_API, headers=headers)
    resp.raise_for_status()
    # Nacos API for namespaces returns 'data', which is a list of namespace dicts
    # Each dict has 'namespace' (ID) and 'namespaceShowName' (name)
    namespaces = resp.json().get("data", [])
    # Return a dictionary mapping namespace ID to the full namespace dict for reliable lookup
    return {ns.get("namespace", ""): ns for ns in namespaces}

def list_files_relative(directory):
    """Lists all files in a directory and its subdirectories with paths relative to the directory."""
    base_path = Path(directory)
    if not base_path.exists():
        # logger.warning(f"Directory '{directory}' does not exist.") # Suppress warning here for horizontal view if one dir is missing
        return set()
    file_list = set()
    # os.walk includes the base directory itself
    for root, _, files in os.walk(directory):
        for file in files:
            # Create the full path, then make it relative to the base directory
            full_path = Path(root) / file
            relative_path = full_path.relative_to(base_path).as_posix()
            file_list.add(relative_path)
    return file_list

def horizontal_tree_compare(export_dir, import_dir, only_in_export, only_in_import, export_prefix='', import_prefix='', is_last_export=True, is_last_import=True):
    """Prints a horizontal comparison of two directory trees."""
    export_path = Path(export_dir)
    import_path = Path(import_dir)

    # Get entries for the current level, excluding hidden ones
    export_entries = sorted([e for e in export_path.iterdir() if not e.name.startswith('.')]) if export_path.exists() else []
    import_entries = sorted([e for e in import_path.iterdir() if not e.name.startswith('.')]) if import_path.exists() else []

    # Combine entries based on name to iterate through
    all_entry_names = sorted(list(set([e.name for e in export_entries] + [e.name for e in import_entries])))

    # Define the tree connectors
    export_branch_connector = '└── ' if is_last_export else '├── '
    export_pipe_connector = '    ' if is_last_export else '│   '

    import_branch_connector = '└── ' if is_last_import else '├── '
    import_pipe_connector = '    ' if is_last_import else '│   '

    # Determine next prefixes for recursion
    export_next_prefix = export_prefix + export_pipe_connector
    import_next_prefix = import_prefix + import_pipe_connector

    column_width = 60  # Fixed width for the export column

    for i, name in enumerate(all_entry_names):
        export_entry = next((e for e in export_entries if e.name == name), None)
        import_entry = next((e for e in import_entries if e.name == name), None)

        is_last_name = i == len(all_entry_names) - 1

        # Determine if the entry is unique to export, import, or exists in both
        unique_to_export = export_entry and not import_entry
        unique_to_import = import_entry and not export_entry
        in_both = export_entry and import_entry

        # Define colors
        green_start = '\033[92m'  # Green for export-only files (to be removed)
        red_start = '\033[91m'    # Red for import-only files (new files)
        color_end = '\033[0m'

        # Build the display strings for export and import sides
        export_display = name  # Always show the name on both sides
        import_display = name  # Always show the name on both sides

        # Add directory marker if it's a directory
        if export_entry and export_entry.is_dir():
            export_display += '/'
        if import_entry and import_entry.is_dir():
            import_display += '/'

        # Add markers for unique entries
        if unique_to_export:
            export_display = f"{green_start}{export_display} [-]{color_end}"
        if unique_to_import:
            import_display = f"{red_start}{import_display} [+]{color_end}"

        # Add tree connectors and prefixes
        export_line = export_prefix + (export_branch_connector if is_last_name else '├── ') + export_display
        import_line = import_prefix + (import_branch_connector if is_last_name else '├── ') + import_display

        # Calculate padding for alignment
        # Strip color codes for accurate length calculation
        export_line_stripped = export_line.replace(green_start, '').replace(color_end, '')
        padding_needed = column_width - len(export_line_stripped)
        if padding_needed < 1:
            padding_needed = 1  # Ensure at least one space

        print(f"{export_line}{' ' * padding_needed}{import_line}")

        # Recurse for directories that exist on either or both sides
        if (export_entry and export_entry.is_dir()) or (import_entry and import_entry.is_dir()):
            horizontal_tree_compare(
                export_entry if export_entry and export_entry.is_dir() else Path("nonexistent_path"),
                import_entry if import_entry and import_entry.is_dir() else Path("nonexistent_path"),
                only_in_export, only_in_import,
                export_prefix=export_next_prefix,
                import_prefix=import_next_prefix,
                is_last_export=is_last_name,
                is_last_import=is_last_name
            )

def main():
    export_dir = 'export'
    import_dir = 'import'

    logger.info(f"Comparing directories: '{export_dir}' and '{import_dir}'")

    logger.info(f"current dir: {os.getcwd()}")

    # List files in each directory to find differences
    export_files = list_files_relative(export_dir)
    import_files = list_files_relative(import_dir)

    # Find files present in export but not in import
    only_in_export = export_files - import_files

    # Find files present in import but not in export
    only_in_import = import_files - export_files

    if only_in_export:
        logger.warning("Found files only in export (candidates for deletion from Nacos if enabled):")
        for f in sorted(list(only_in_export)):
            print(f"\033[92m[-] {f}\033[0m")  # Green for files to be removed
    else:
        logger.info("No files found only in export.")

    if only_in_import:
        logger.info("Found files only in import (candidates for addition/update in Nacos if enabled):")
        for f in sorted(list(only_in_import)):
            print(f"\033[91m[+] {f}\033[0m")  # Red for new files
    else:
        logger.info("No files found only in import.")

    print("\nExport vs Import Comparison:")
    horizontal_tree_compare(export_dir, import_dir, only_in_export, only_in_import)

    # --- Nacos Synchronization Logic (Import to Nacos) ---
    if NACOS_SYNC_IMPORT:
        logger.info("\nNACOS_SYNC_IMPORT is true. Checking for configurations to add/update in Nacos from import.")
        headers = get_nacos_headers()
        
        # For simplicity initially, let's consider files only in import as candidates for adding.
        # A more robust approach would involve fetching all Nacos configs and comparing content
        # of files present in both import and Nacos.
        
        configs_to_add_or_update = only_in_import # Start with files only in import
        
        # TODO: Add logic here to find files present in both import and export (or just import and Nacos)
        # but with different content compared to Nacos.
        
        if configs_to_add_or_update:
             logger.info(f"Found {len(configs_to_add_or_update)} configurations in import to add/update in Nacos. Proceeding...")
             for file_path in configs_to_add_or_update:
                 full_import_path = Path(import_dir) / file_path
                 if full_import_path.is_file():
                    try:
                         with open(full_import_path, 'r', encoding='utf-8') as f:
                             content = f.read()

                         parts = Path(file_path).parts
                         # Assuming structure <namespace>/<group>/<dataId> or <namespace>/<dataId> relative to the import directory
                         if len(parts) >= 2:
                             namespace_name = parts[0]
                             group = "" # Default group
                             data_id_parts = []

                             if len(parts) >= 3:
                                 # Structure is <namespace>/<group>/<dataId>
                                 group = parts[1]
                                 data_id_parts = parts[2:]
                             else:
                                 # Structure is <namespace>/<dataId>, assume default group
                                 data_id_parts = parts[1:]

                             data_id = "/".join(data_id_parts) if data_id_parts else ""

                             # Need to map namespace name to Nacos namespace ID for the publish API.
                             # Fetch Nacos namespaces once before the loop.
                             # For now, let's fetch here, but it's inefficient.

                             try:
                                 current_nacos_namespaces = get_namespaces(headers)
                             except requests.exceptions.RequestException as e:
                                 logger.error(f"Failed to fetch current Nacos namespaces for publish logic: {e}")
                                 logger.warning("Skipping this configuration.")
                                 continue

                             nacos_namespace_id_for_publish = '' # Default for public if matched
                             found_namespace_id = False
                             for ns_id, ns_details in current_nacos_namespaces.items():
                                 if ns_details.get("namespaceShowName") == namespace_name:
                                     nacos_namespace_id_for_publish = ns_id
                                     found_namespace_id = True
                                     break

                             if not found_namespace_id and namespace_name != 'public':
                                 logger.warning(f"Namespace '{namespace_name}' from import not found in current Nacos namespaces. Cannot publish config: {file_path}")
                                 continue # Skip if namespace from import isn't found in Nacos

                             # If the namespace is 'public', ensure we use the correct Nacos ID ('', 'public')
                             if namespace_name == 'public':
                                  public_ns_details = current_nacos_namespaces.get('') or current_nacos_namespaces.get('public')
                                  if public_ns_details:
                                       nacos_namespace_id_for_publish = public_ns_details.get("namespace", "")
                                  else:
                                       logger.warning(f"Public namespace from import not found in current Nacos namespaces. Cannot publish config: {file_path}")
                                       continue

                             if data_id:
                                try:
                                     publish_nacos_config(data_id, group, nacos_namespace_id_for_publish, content, headers)
                                     logger.info(f"Successfully published/updated {namespace_name}/{group}/{data_id} in Nacos.")
                                except requests.exceptions.RequestException as e:
                                     logger.error(f"Failed to publish/update {namespace_name}/{group}/{data_id} in Nacos: {e}")
                             else:
                                  logger.warning(f"Skipping publish for invalid path structure in import: {file_path}")
                    except Exception as e:
                         logger.error(f"Error reading file {file_path} or processing for publish: {e}")
                 else:
                     logger.warning(f"Skipping publish for non-file entry in import: {file_path}")
        else:
            logger.info("No new or changed configurations found in import to publish.")

    # --- Nacos Deletion Logic (Export Only) ---
    if NACOS_DELETE_EXPORT_ONLY:
        logger.info("NACOS_DELETE_EXPORT_ONLY is true. Checking for configurations to delete from Nacos.")
        headers = get_nacos_headers()
        
        # Fetch current Nacos namespaces ONCE before starting deletion loops
        try:
            current_nacos_namespaces = get_namespaces(headers)
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch current Nacos namespaces: {e}")
            logger.error("Skipping Nacos deletion tasks.")
            return # Exit main if we can't even get the namespace list

        export_only_configs = export_files - import_files

        if export_only_configs:
            logger.info(f"Found {len(export_only_configs)} configurations in export but not in import. Proceeding with deletion from Nacos.")
            for file_path in export_only_configs:
                parts = Path(file_path).parts
                # Assuming structure <namespace>/<group>/<dataId> or <namespace>/<dataId> relative to the export directory
                if len(parts) >= 2:
                    namespace_name = parts[0]
                    group = "" # Default group
                    data_id_parts = []

                    if len(parts) >= 3:
                        # Structure is <namespace>/<group>/<dataId>
                        group = parts[1]
                        data_id_parts = parts[2:]
                    else:
                        # Structure is <namespace>/<dataId>, assume default group
                        data_id_parts = parts[1:]

                    data_id = "/".join(data_id_parts) if data_id_parts else ""

                    # Map namespace name back to Nacos namespace ID.
                    # Use the corrected get_namespaces to find the ID by name.
                    nacos_namespace_id_to_delete = '' # Default for public if found
                    found_namespace_id = False
                    for ns_id, ns_details in current_nacos_namespaces.items():
                         if ns_details.get("namespaceShowName") == namespace_name:
                             nacos_namespace_id_to_delete = ns_id
                             found_namespace_id = True
                             break

                    if not found_namespace_id and namespace_name != 'public':
                         logger.warning(f"Namespace '{namespace_name}' from export not found in current Nacos namespaces. Skipping config deletion for this namespace.")
                         continue # Skip this config if the namespace isn't found in Nacos
                    
                    # If the namespace is 'public', use empty string for Nacos API if that's its actual ID
                    if namespace_name == 'public':
                         # Find the actual public namespace ID (could be '' or 'public')
                         public_ns_details = current_nacos_namespaces.get('') or current_nacos_namespaces.get('public')
                         if public_ns_details:
                              nacos_namespace_id_to_delete = public_ns_details.get("namespace", "")
                         else:
                             logger.warning(f"Public namespace from export not found in current Nacos namespaces. Skipping config deletion.")
                             continue

                    if data_id:
                        try:
                            delete_nacos_config(data_id, group, nacos_namespace_id_to_delete, headers)
                            logger.info(f"Successfully deleted {nacos_namespace_id_to_delete}/{group}/{data_id} from Nacos.")
                        except requests.exceptions.RequestException as e:
                            logger.error(f"Failed to delete {nacos_namespace_id_to_delete}/{group}/{data_id} from Nacos: {e}")
                    else:
                         logger.warning(f"Skipping deletion for invalid path structure: {file_path}")
        else:
            logger.info("No configurations found in export only. No deletions needed.")

        # Logic to delete empty namespaces from Nacos
        logger.info("Checking for empty namespaces in Nacos to delete.")
        # current_nacos_namespaces is already fetched above and maps ID to details
        
        try:
            # Iterate through actual Nacos namespaces (excluding public) to check for emptiness
            for ns_id, ns_details in current_nacos_namespaces.items():
                ns_name = ns_details.get("namespaceShowName", ns_id) # Get display name or use ID if missing

                # Skip the public namespace
                # Nacos public namespace ID is usually '' or 'public', and its display name is typically 'public' or 'public(to retain control)'
                # We will skip based on both ID and common display names to be safe.
                if ns_id == '' or ns_id == 'public' or ns_name in ['public', 'public(to retain control)']:
                    logger.info(f"Skipping empty check and deletion for public namespace (ID: {ns_id}, Name: '{ns_name}').")
                    continue
                
                logger.info(f"Checking namespace '{ns_name}' (ID: {ns_id}) for emptiness in Nacos.")

                # Use the Nacos Namespace ID to get the config list
                nacos_namespace_id_for_check = ns_id
                
                try:
                    config_list_response = get_nacos_config_list(nacos_namespace_id_for_check, headers)
                    total_configs = config_list_response.get("totalCount", 0)
                except requests.exceptions.RequestException as e:
                     logger.error(f"Failed to get config list for namespace '{ns_name}' ({ns_id}): {e}")
                     logger.warning(f"Skipping empty check and deletion for namespace '{ns_name}'.")
                     continue

                logger.info(f"Namespace '{ns_name}' (ID: {ns_id}) contains {total_configs} configurations.")

                if total_configs == 0:
                     # Delete if it's empty and not the public namespace (already checked)
                     # Also, DO NOT delete if a corresponding directory exists in the 'import' folder
                     import_namespace_path = Path(import_dir) / ns_name
                     if import_namespace_path.is_dir():
                         logger.info(f"Skipping deletion of empty Nacos namespace '{ns_name}' (ID: {ns_id}) because a corresponding directory exists in '{import_dir}'.")
                     else:
                         try:
                            logger.info(f"Namespace '{ns_name}' (ID: {ns_id}) is empty in Nacos and no corresponding directory in '{import_dir}'. Attempting to delete...")
                            delete_nacos_namespace(ns_id, headers)
                            logger.info(f"Successfully deleted namespace '{ns_name}' (ID: {ns_id}) from Nacos.")
                         except requests.exceptions.RequestException as e:
                            logger.error(f"Failed to delete namespace '{ns_name}' (ID: {ns_id}) from Nacos: {e}")
                else:
                    logger.info(f"Namespace '{ns_name}' (ID: {ns_id}) contains {total_configs} configurations. Not deleting.")

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed during empty namespace check or deletion: {e}")

    else:
        logger.info("NACOS_DELETE_EXPORT_ONLY is false. Skipping deletion logic.")

if __name__ == "__main__":
    main()
