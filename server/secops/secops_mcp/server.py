# Copyright 2025 Google LLC
# Licensed under the Apache License, Version 2.0.
"""Google Security Operations MCP server."""

import json
import logging
import os
import sys
from typing import Any, Optional
from mcp.server.fastmcp import FastMCP
from secops import SecOpsClient

server = FastMCP("Google Security Operations MCP server", log_level="ERROR")

# Configure logging to stdout so we can see errors in Cloud Logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger("secops-mcp")

DEFAULT_PROJECT_ID = os.environ.get("CHRONICLE_PROJECT_ID", "725716774503")
DEFAULT_CUSTOMER_ID = os.environ.get("CHRONICLE_CUSTOMER_ID", "c3c6260c1c9340dcbbb802603bbf9636")
DEFAULT_REGION = os.environ.get("CHRONICLE_REGION", "us")

def get_chronicle_client(
    project_id: Optional[str] = None, 
    customer_id: Optional[str] = None, 
    region: Optional[str] = None
) -> Any:
    project_id = project_id or DEFAULT_PROJECT_ID
    customer_id = customer_id or DEFAULT_CUSTOMER_ID
    region = region or DEFAULT_REGION

    if not project_id or not customer_id:
        logger.error("Missing Project ID or Customer ID")
        return None

    # 1. Determine the directory where THIS script lives
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. Look for the key file in the same directory
    # We ignore the env var path to prevent relative path confusion in the cloud
    sa_key_path = os.path.join(base_dir, "service_account.json")

    logger.info(f"Attempting to load SA Key from: {sa_key_path}")

    if not os.path.exists(sa_key_path):
        logger.error(f"CRITICAL: Key file NOT found at {sa_key_path}")
        # List directory contents to help debug
        try:
            logger.info(f"Contents of {base_dir}: {os.listdir(base_dir)}")
        except:
            pass
        return None

    try:
        with open(sa_key_path, 'r') as f:
            service_account_info = json.load(f)

        logger.info(f"Initializing SecOps Client for Region: {region}")
        client = SecOpsClient(service_account_info=service_account_info)
        chronicle = client.chronicle(customer_id=customer_id, project_id=project_id, region=region)
        return chronicle
    except Exception as e:
        logger.error(f"Failed to initialize SecOps client: {e}")
        import traceback
        traceback.print_exc()
        return None

from secops_mcp.tools import *

def main() -> None:
    server.run(transport="stdio")

if __name__ == "__main__":
    main()
