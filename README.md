# Build Your Own Agentic SOC powered by Gemini Enterprise

This repository contains the code and instructions to deploy a **Google Security Agent**. This agent utilizes Google Vertex AI (Reasoning Engine), Google SecOps (Chronicle), SecOps SOAR, and VirusTotal to act as an intelligent assistant for security operations.

## 📋 Prerequisites

Before starting, ensure you have the following information ready:

1.  **Google Cloud Project ID** (Where you have Editor/Owner permissions).
2.  **Google SecOps (Chronicle) Details:**
    * **Customer ID** (Found in SecOps Console > Settings > Profile).
    * **Region** (e.g., `us`, `asia-southeast1`, `australia-southeast1`).
3.  **SecOps SOAR Details:**
    * **Instance URL** (With the Google SecOps console in the current browser window, open Developer Tools -> Network Tab, filter for `siemplify-soar`. Refresh the page to see the URL requests).
    * **API Key** (Found in SecOps SOAR Console > Settings > Advanced > API Keys).
4.  **VirusTotal (GTI) API Key:**
    * Get it from [VirusTotal API Key Settings](https://www.virustotal.com/gui/my-apikey).

---

## 🚀 Deployment Guide

### Phase 1: Environment Setup & IAM

**1. Open Cloud Shell**
Navigate to your Google Cloud Project console and activate Cloud Shell.

**2. Initialize Environment**
Run the following commands to set the project context, enable APIs, clone the repo, and setup the staging bucket.

```bash
# Set Project Context
export PROJECT_ID=$(gcloud config get-value project)
gcloud config set project $PROJECT_ID

# Enable APIs
gcloud services enable aiplatform.googleapis.com storage.googleapis.com \
    cloudbuild.googleapis.com compute.googleapis.com discoveryengine.googleapis.com \
    securitycenter.googleapis.com iam.googleapis.com

# Clone Repo & Setup Bucket
echo "--- Setting up Environment ---"
cd ~
rm -rf mcp-security # Clean start if needed
git clone https://github.com/SumitsWorkshopOrg/agentic-soc.git
cd agentic-soc/run-with-google-adk/

echo "--- Installing Dependencies ---"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
chmod +x run-adk-agent.sh ae_deploy_run.sh

echo "--- Creating Staging Bucket ---"
BUCKET_NAME="${PROJECT_ID}-staging-bucket"
if gsutil ls -b gs://$BUCKET_NAME > /dev/null 2>&1; then
    echo "✅ Bucket gs://$BUCKET_NAME already exists."
else
    echo "Creating gs://$BUCKET_NAME..."
    gcloud storage buckets create gs://$BUCKET_NAME --location=us-central1
fi
echo "✅ Environment Ready."
```

**3. Configure IAM Permissions**
This step ensures the Vertex AI and Reasoning Engine service agents have access to the staging bucket.

```bash
# Copy and paste this block into Cloud Shell
echo "--- 🛠️ Setting up Service Agent Permissions ---"
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
BUCKET_NAME="${PROJECT_ID}-staging-bucket"

# Trigger Service Agent Creation
gcloud beta services identity create --service=aiplatform.googleapis.com --project=$PROJECT_ID 2>/dev/null
gcloud beta services identity create --service=discoveryengine.googleapis.com --project=$PROJECT_ID 2>/dev/null

# Define Agent Emails
VERTEX_SA="service-${PROJECT_NUMBER}@gcp-sa-aiplatform.iam.gserviceaccount.com"
RE_SA="service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
DISCOVERY_SA="service-${PROJECT_NUMBER}@gcp-sa-discoveryengine.iam.gserviceaccount.com"

# Grant Bucket Access
echo "Granting Bucket Access..."
gcloud storage buckets add-iam-policy-binding gs://$BUCKET_NAME --member="serviceAccount:${VERTEX_SA}" --role="roles/storage.objectViewer" >/dev/null
gcloud storage buckets add-iam-policy-binding gs://$BUCKET_NAME --member="serviceAccount:${RE_SA}" --role="roles/storage.objectViewer" >/dev/null 2>&1 || echo "⚠️ Reasoning Engine Agent not ready yet."

# Grant Discovery Engine Permissions
echo "Granting Discovery Engine Permissions..."
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:${DISCOVERY_SA}" --role="roles/aiplatform.user" --condition=None >/dev/null
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:${DISCOVERY_SA}" --role="roles/aiplatform.viewer" --condition=None >/dev/null
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:${DISCOVERY_SA}" --role="roles/discoveryengine.serviceAgent" --condition=None >/dev/null

echo "✅ Permissions fixed. Waiting 15 seconds for propagation..."
sleep 15
```

### Phase 2: Credential Injection (Option A)
Run the following block to create a dedicated Service Account for the agent, assign it permissions, and save the key file directly into the server directory.

```bash
(
    echo "--- Option A: Automated Credential Setup ---"
    PROJECT_ID=$(gcloud config get-value project)
    SA_NAME="chronicle-svc-acct"
    SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
    
    # Define where the key goes (inside the server module)
    TARGET_DIR="../server/secops/secops_mcp"
    KEY_FILENAME="service_account.json"
    FULL_KEY_PATH="${TARGET_DIR}/${KEY_FILENAME}"

    echo "1. Creating/Verifying Service Account..."
    gcloud resource-manager org-policies disable-enforce iam.disableServiceAccountKeyCreation --project=$PROJECT_ID
    if ! gcloud iam service-accounts describe $SA_EMAIL > /dev/null 2>&1; then
        gcloud iam service-accounts create $SA_NAME --display-name="Chronicle Service Account"
    fi

    echo "2. Assigning Permissions..."
    gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:${SA_EMAIL}" --role="roles/chronicle.viewer" --condition=None > /dev/null 2>&1
    gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:${SA_EMAIL}" --role="roles/chronicle.serviceAgent" --condition=None > /dev/null 2>&1
    gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:${SA_EMAIL}" --role="roles/aiplatform.user" --condition=None > /dev/null 2>&1

    echo "3. Generating Key..."
    # Create the key directly in the server folder
    gcloud iam service-accounts keys create "$FULL_KEY_PATH" --iam-account=$SA_EMAIL
    
    echo "✅ Key saved to: $FULL_KEY_PATH"
)
```

### Phase 3: Configuration & Deployment
Run this block to configure your environment variables and deploy the Agent Engine to Vertex AI. **This step takes 5-10 minutes.**

```bash
echo "--- Configure Agent Environment ---" && \
read -p "Enter Chronicle Customer ID: " CHRONICLE_CUSTOMER_ID && \
read -p "Enter VirusTotal API Key: " VT_APIKEY && \
read -p "Enter SOAR URL: " SOAR_URL && \
read -p "Enter SOAR App Key: " SOAR_APP_KEY && \
read -p "Enter Google API Key (Press Enter to skip if using Vertex AI): " GOOGLE_API_KEY && \
[ -z "$GOOGLE_API_KEY" ] && GOOGLE_API_KEY="NOT_SET"; \
PROJECT_ID=$(gcloud config get-value project) && \
AE_STAGING_BUCKET="${PROJECT_ID}-staging-bucket" && \

# Write .env file
cat <<EOC > google_mcp_security_agent/.env
APP_NAME=google_mcp_security_agent
LOCAL_DIR_FOR_FILES=/tmp
MAX_PREV_USER_INTERACTIONS=3
AE_STAGING_BUCKET=$AE_STAGING_BUCKET
LOAD_SECOPS_MCP=Y
CHRONICLE_PROJECT_ID=$PROJECT_ID
CHRONICLE_CUSTOMER_ID=$CHRONICLE_CUSTOMER_ID
CHRONICLE_REGION=us
CHRONICLE_SERVICE_ACCOUNT_FILE=secops_mcp/service_account.json
LOAD_GTI_MCP=Y
VT_APIKEY=$VT_APIKEY
LOAD_SECOPS_SOAR_MCP=Y
SOAR_URL=$SOAR_URL
SOAR_APP_KEY=$SOAR_APP_KEY
LOAD_SCC_MCP=Y
GOOGLE_GENAI_USE_VERTEXAI=True
GOOGLE_API_KEY=$GOOGLE_API_KEY
GOOGLE_MODEL=gemini-2.5-flash
GOOGLE_CLOUD_PROJECT=$PROJECT_ID
GOOGLE_CLOUD_LOCATION=us-central1
STDIO_PARAM_TIMEOUT=60.0
MINIMAL_LOGGING=N
EOC

echo "✅ Configuration saved." && \
cp google_mcp_security_agent/.env .env && \
echo "🚀 Starting Deployment..." && \
./ae_deploy_run.sh 2>&1 | tee deploy.log && \
RESOURCE_NAME=$(grep -o "projects/.*/locations/.*/reasoningEngines/[0-9]*" deploy.log | tail -n 1) && \
if [ ! -z "$RESOURCE_NAME" ]; then
    echo "" >> .env
    echo "AGENT_ENGINE_RESOURCE_NAME=$RESOURCE_NAME" >> .env
    echo "✅ Auto-captured Resource Name: $RESOURCE_NAME"
else
    echo "⚠️ Could not auto-capture Resource Name. Copy it manually from the log."
fi
```

### Phase 4: Gemini Enterprise Registration
**1. Create App:**
* Search for **Gemini Enterprise** in the Cloud Console.
* Click **Create your first app**.
* **Name:** SecOps Agent.
* **Region:** Global.
* **Copy the App ID** (e.g., `gemini-enterprise-xxxx`).
* Click **Create**.
* Select **Set up identity** -> **Use Google Identity** -> **Confirm**.

**2. Register Agent & Set Permissions:**
Run this final script in Cloud Shell to connect your deployed engine to the Gemini App and grant users access.

```bash
echo "--- Register Gemini Agent & Set Permissions ---"
if [ -f .env ]; then source .env; fi

# 1. Gather Configuration
read -p "Enter Gemini Enterprise App ID (from UI): " AGENT_SPACE_APP_NAME
if [ -z "$AGENT_ENGINE_RESOURCE_NAME" ]; then
    read -p "Enter Agent Engine Resource Name (from deploy log): " REASONING_ENGINE_RESOURCE
else
    REASONING_ENGINE_RESOURCE=$AGENT_ENGINE_RESOURCE_NAME
    echo "✅ Found Agent Engine Resource: $REASONING_ENGINE_RESOURCE"
fi

# 2. Ask for Access Permissions
echo -e "\nWho should be able to use this agent?"
echo " - Entire Organization:  domain:yourdomain.com (e.g., domain:google.com)"
echo " - Specific Group:       group:security-team@yourdomain.com"
echo " - Just Me (Skip):       (Press Enter)"
read -p "Enter Principal Identifier: " AGENT_PRINCIPAL

PROJECT_ID=$(gcloud config get-value project)
ACCESS_TOKEN=$(gcloud auth print-access-token)
TARGET_URL="https://discoveryengine.googleapis.com/v1alpha/projects/${PROJECT_ID}/locations/global/collections/default_collection/engines/${AGENT_SPACE_APP_NAME}/assistants/default_assistant/agents"

# 3. Create the Agent
echo "Creating Agent..."
JSON_DATA=$(cat <<EOJ
{
    "displayName": "Google Security Agent",
    "description": "Allows security operations on Google Security Products",
    "adk_agent_definition": {
        "tool_settings": {
            "tool_description": "Various Tools from SIEM, SOAR and SCC"
        },
        "provisioned_reasoning_engine": {
            "reasoning_engine": "${REASONING_ENGINE_RESOURCE}"
        }
    }
}
EOJ
)

# Run creation and capture output
RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  -d "$JSON_DATA" "$TARGET_URL")

CREATED_AGENT_NAME=$(echo "$RESPONSE" | grep -o '"name": "[^"]*"' | head -n 1 | cut -d'"' -f4)

if [ -z "$CREATED_AGENT_NAME" ]; then
    echo "❌ Error Creating Agent. API Response:"
    echo "$RESPONSE"
else
    echo "✅ Agent Created: $CREATED_AGENT_NAME"

    # 4. Apply Permissions (if a principal was provided)
    if [ ! -z "$AGENT_PRINCIPAL" ]; then
        echo "Granting 'Agent User' role to $AGENT_PRINCIPAL..."
        
        POLICY_URL="https://discoveryengine.googleapis.com/v1alpha/${CREATED_AGENT_NAME}:setIamPolicy"
        POLICY_DATA=$(cat <<EOP
{
  "policy": {
    "bindings": [
      {
        "role": "roles/discoveryengine.agentUser",
        "members": [ "${AGENT_PRINCIPAL}" ]
      }
    ]
  }
}
EOP
        )

        PERM_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" \
          -H "Authorization: Bearer $ACCESS_TOKEN" \
          -H "X-Goog-User-Project: ${PROJECT_ID}" \
          -d "$POLICY_DATA" "$POLICY_URL")

        if echo "$PERM_RESPONSE" | grep -q "etag"; then
            echo "✅ Permissions applied successfully."
        else
            echo "⚠️  Warning: Failed to apply permissions."
            echo "Response: $PERM_RESPONSE"
        fi
    fi
    echo -e "\n🎉 Agent Registration Complete!"
fi
```

### Usage
1. Go to the **Gemini Enterprise** console.
2. Open your App.
3. In the menu, go to **Agents** or **Agent Gallery**.
4. Find **Google Security Agent** under "From your organization".
5. Pin the agent and select it.
6. Start chatting!

### Example Prompts:
- "Find logon events from the last 3 days."
- "Summarize the high severity alerts."

### Troubleshooting
- **"Something went wrong..." error:** Wait 1-2 minutes and refresh the page. The agent engine may still be initializing.
- **"Failed to create session":** Ensure your Model Name is set to `gemini-2.5-flash` in the `.env` file and that you have redeployed.
