# Copyright 2025 Google LLC
# Licensed under the Apache License, Version 2.0.
"""Google Security Operations MCP server."""

import json
import logging
import os
from typing import Any, Optional
from mcp.server.fastmcp import FastMCP
from secops import SecOpsClient
 
server = FastMCP("Google Security Operations MCP server", log_level="ERROR")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("secops-mcp")
USER_AGENT = "secops-app/1.0"

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
        raise ValueError("Chronicle project_id and customer_id must be provided.")

    # PLACEHOLDER: This will be replaced by the attendee's credentials script
    sa_json_string = r"""
    {
      "type": "service_account",
      "project_id": "PLACEHOLDER",
      "private_key_id": "PLACEHOLDER",
      "private_key": "-----BEGIN PRIVATE KEY-----\nPLACEHOLDER\n-----END PRIVATE KEY-----\n",
      "client_email": "PLACEHOLDER",
      "client_id": "PLACEHOLDER",
      "auth_uri": "https://accounts.google.com/o/oauth2/auth",
      "token_uri": "https://oauth2.googleapis.com/token",
      "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
      "client_x509_cert_url": "PLACEHOLDER",
      "universe_domain": "googleapis.com"
    }
    """
    
    # Parse the JSON string
    try:
        service_account_info = json.loads(sa_json_string) 
        if "private_key" in service_account_info:
            service_account_info["private_key"] = service_account_info["private_key"].replace("\\n", "\n")
        client = SecOpsClient(service_account_info=service_account_info)
        chronicle = client.chronicle(customer_id=customer_id, project_id=project_id, region=region)
        return chronicle
    except Exception:
        # Fallback if placeholder is invalid (expected during initial repo checkout)
        return None

from secops_mcp.tools import *

def main() -> None:
    server.run(transport="stdio")

if __name__ == "__main__":
    main()
