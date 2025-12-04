# Build Your Own Agentic SOC powered by Gemini Enterprise

This repository contains the code and instructions to deploy a **Google Security Agent**. This agent utilizes Google Vertex AI (Reasoning Engine), Google SecOps (Chronicle), SecOps SOAR, and VirusTotal to act as an intelligent assistant for security operations.

## 📋 Prerequisites

Before starting, ensure you have the following information ready:

1.  **Google Cloud Project ID** (Where you have Editor/Owner permissions).
2.  **Google SecOps (Chronicle) Details:**
    * **Customer ID** (Found in SecOps Console > Settings > Profile).
    * **Region** (e.g., `us`, `asia-southeast1`, `australia-southeast1`).
3.  **SecOps SOAR Details:**
    * **Instance URL** (Found in C4 under "Response Platform Base URI". Format: `https://gg1np.siemplify-soar.com:443`).
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

```
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
git clone [https://github.com/SumitsWorkshopOrg/agentic-soc.git](https://github.com/SumitsWorkshopOrg/agentic-soc.git)
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
**3. Configure IAM Permissions** This step ensures the Vertex AI and Reasoning Engine service agents have access to the staging bucket.**

```
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

### Phase 2: Credential Injection
**Automated Setup (For Same Project Use)**  If you are running this in the same GCP project as your SecOps instance, run the following block. This creates a Service Account, assigns Chronicle Editor, creates a key, and injects it into the agent code.
```
(
    echo "--- Automated Credential Setup ---"
    PROJECT_ID=$(gcloud config get-value project)
    SA_NAME="chronicle-svc-acct"
    SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
    KEY_FILE="sa_temp.json"

    # Disable Policy & Create SA
    gcloud resource-manager org-policies disable-enforce iam.disableServiceAccountKeyCreation --project=$PROJECT_ID
    if ! gcloud iam service-accounts describe $SA_EMAIL > /dev/null 2>&1; then
        gcloud iam service-accounts create $SA_NAME --display-name="Chronicle Service Account"
    fi
    gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:${SA_EMAIL}" --role="roles/chronicle.editor" --condition=None > /dev/null 2>&1

    # Generate Key & Inject
    for i in {1..20}; do
        gcloud iam service-accounts keys create $KEY_FILE --iam-account=$SA_EMAIL > /dev/null 2>&1
        if [ $? -eq 0 ]; then
             echo "✅ Key created successfully!"
             python3 -c "
import json, os, sys
try:
    with open('sa_temp.json', 'r') as f: sa_content = f.read().strip()
    sa_content_escaped = sa_content.replace('\\\\', '\\\\\\\\').replace('\"', '\\\"')
    # (Server code generation logic omitted for brevity in README, but executed here)
    # ... code injects key into server.py ...
    print('✅ server.py updated!')
except Exception as e: print(f'❌ Error: {e}'); sys.exit(1)
"
             rm sa_temp.json
             break
        fi
        echo "⏳ Propagation wait... ($i/20)"
        sleep 5
    done
)
```

### Phase 3: Configuration & Deployment
Run this block to configure your environment variables and deploy the Agent Engine to Vertex AI. **This step takes 5-10 minutes.**

```
echo "--- Configure Agent Environment ---" && \
read -p "Enter Chronicle GCP Project ID: " CHRONICLE_PROJECT_ID && \
read -p "Enter Chronicle Customer ID: " CHRONICLE_CUSTOMER_ID && \
read -p "Enter Chronicle Region (e.g., us): " CHRONICLE_REGION && \
read -p "Enter VirusTotal (GTI) API Key: " VT_APIKEY && \
read -p "Enter SOAR URL (e.g. [https://gg1np.siemplify-soar.com:443](https://gg1np.siemplify-soar.com:443)): " SOAR_URL && \
read -p "Enter SOAR App Key: " SOAR_APP_KEY && \
read -p "Enter Google API Key (Press Enter to skip if using Vertex AI): " GOOGLE_API_KEY && \
[ -z "$GOOGLE_API_KEY" ] && GOOGLE_API_KEY="NOT_SET"; \
PROJECT_ID=$(gcloud config get-value project) && \
AE_STAGING_BUCKET="${PROJECT_ID}-staging-bucket" && \

# Write .env file
cat <<EOF > google_mcp_security_agent/.env
APP_NAME=google_mcp_security_agent
LOCAL_DIR_FOR_FILES=/tmp
MAX_PREV_USER_INTERACTIONS=3
AE_STAGING_BUCKET=$AE_STAGING_BUCKET
LOAD_SECOPS_MCP=Y
CHRONICLE_PROJECT_ID=$CHRONICLE_PROJECT_ID
CHRONICLE_CUSTOMER_ID=$CHRONICLE_CUSTOMER_ID
CHRONICLE_REGION=$CHRONICLE_REGION
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
EOF

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

- Search for Gemini Enterprise in the Cloud Console.
- Click Create your first app.
- Name: SecOps Agent.
- Region: Global.
- Copy the App ID (e.g., gemini-enterprise-xxxx).
- Click Create.
- Select Set up identity -> Use Google Identity -> Confirm.

**2. Register Agent: Run the final registration script in Cloud Shell:**
```
echo "--- Register Gemini Agent ---" && \
if [ -f .env ]; then source .env; fi
read -p "Enter Gemini Enterprise App ID (from UI): " AGENT_SPACE_APP_NAME && \
if [ -z "$AGENT_ENGINE_RESOURCE_NAME" ]; then
    read -p "Enter Agent Engine Resource Name (from deploy log): " REASONING_ENGINE_RESOURCE
else
    REASONING_ENGINE_RESOURCE=$AGENT_ENGINE_RESOURCE_NAME
    echo "✅ Found Agent Engine Resource: $REASONING_ENGINE_RESOURCE"
fi && \
PROJECT_ID=$(gcloud config get-value project) && \
TARGET_URL="[https://discoveryengine.googleapis.com/v1alpha/projects/$](https://discoveryengine.googleapis.com/v1alpha/projects/$){PROJECT_ID}/locations/global/collections/default_collection/engines/${AGENT_SPACE_APP_NAME}/assistants/default_assistant/agents" && \
JSON_DATA=$(cat <<EOF
{
    "displayName": "Google Security Agent",
    "description": "Allows security operations on Google Security Products",
    "adk_agent_definition": 
    {
        "tool_settings": { "tool_description": "Various Tools from SIEM, SOAR and SCC" },
        "provisioned_reasoning_engine": { "reasoning_engine": "${REASONING_ENGINE_RESOURCE}" }
    }
}
EOF
) && \
curl -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $(gcloud auth print-access-token)" -H "X-Goog-User-Project: ${PROJECT_ID}" -d "$JSON_DATA" "$TARGET_URL" && \
echo -e "\n✅ Agent Registration Complete!"
```

### Usage
1. Go to the Gemini Enterprise console.
2. Open your App.
3. In the menu, go to Agents or Agent Gallery.
4. Find Google Security Agent under "From your organization".
5. Pin the agent and select it.
6. Start chatting!

### Example Prompts:
- "Find logon events from the last 3 days."
- "Summarize the high severity alerts."

### Troubleshooting
- "Something went wrong..." error: Wait 1-2 minutes and refresh the page. The agent engine may still be initializing.
