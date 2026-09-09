#!/usr/bin/env bash
# Provisions everything needed for the "AI & Automation: Production-Ready AI
# Agents on Azure" 3-day demo repo: Foundry (AI Services) project + model
# deployment, Azure AI Search, Storage, Function App, Application Insights,
# and the RBAC role assignments your signed-in user needs to run the demos
# with DefaultAzureCredential() (no keys in code).
#
# Review every line before running. Nothing here is destructive to existing
# resources — it only creates new ones under a dedicated resource group.
#
# Usage:
#   az login
#   ./setup.sh
#
# Cleanup:
#   ./teardown.sh

set -euo pipefail

# ---- Config (edit these) ----------------------------------------------
LOCATION="eastus2"                       # Foundry model availability varies by region
RG="rg-ai-agent-demo"
FOUNDRY_NAME="aif-agent-demo-11417"      # already created; reused to avoid orphaning a resource
SEARCH_NAME="srch-agent-demo-$RANDOM"
STORAGE_NAME="stagentdemo$RANDOM"        # must be globally unique, lowercase, no dashes
FUNCTION_NAME="func-agent-demo-$RANDOM"
APPINSIGHTS_NAME="appi-agent-demo"
MODEL_DEPLOYMENT_NAME="gpt-5-mini"
MODEL_NAME="gpt-5-mini"
MODEL_VERSION="2025-08-07"               # check `az cognitiveservices account list-models` if this fails
# -------------------------------------------------------------------------

echo "Signed in as:"
az account show --query "{user:user.name, subscription:name}" -o table

echo "==> Creating resource group $RG in $LOCATION"
az group create --name "$RG" --location "$LOCATION" -o none

echo "==> Creating Azure AI Foundry (AIServices) resource: $FOUNDRY_NAME"
az cognitiveservices account create \
  --name "$FOUNDRY_NAME" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --kind AIServices \
  --sku S0 \
  --custom-domain "$FOUNDRY_NAME" \
  --yes -o none

echo "==> Creating Foundry project (required for the Agent Service — the AIServices account alone is not enough)"
az cognitiveservices account project create \
  --name "$FOUNDRY_NAME" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --project-name "agent-demo-project" \
  --display-name "Agent Demo Project" -o none

echo "==> Deploying model $MODEL_NAME ($MODEL_VERSION) as '$MODEL_DEPLOYMENT_NAME'"
az cognitiveservices account deployment create \
  --name "$FOUNDRY_NAME" \
  --resource-group "$RG" \
  --deployment-name "$MODEL_DEPLOYMENT_NAME" \
  --model-name "$MODEL_NAME" \
  --model-version "$MODEL_VERSION" \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name "GlobalStandard" -o none

echo "==> Creating Azure AI Search (Basic tier): $SEARCH_NAME"
az search service create \
  --name "$SEARCH_NAME" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --sku Basic \
  --partition-count 1 \
  --replica-count 1 \
  --auth-options aadOrApiKey \
  --aad-auth-failure-mode http401WithBearerChallenge -o none

echo "==> Creating Storage account (Functions backing store): $STORAGE_NAME"
az storage account create \
  --name "$STORAGE_NAME" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --sku Standard_LRS -o none

echo "==> Creating Application Insights: $APPINSIGHTS_NAME"
az monitor app-insights component create \
  --app "$APPINSIGHTS_NAME" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --kind web \
  --application-type web -o none

echo "==> Creating Function App (Consumption, Python): $FUNCTION_NAME"
az functionapp create \
  --name "$FUNCTION_NAME" \
  --resource-group "$RG" \
  --storage-account "$STORAGE_NAME" \
  --consumption-plan-location "$LOCATION" \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --os-type Linux \
  --app-insights "$APPINSIGHTS_NAME" -o none

echo "==> Enabling system-assigned managed identity on the Function App"
az functionapp identity assign \
  --name "$FUNCTION_NAME" \
  --resource-group "$RG" -o none

# ---- RBAC: let YOUR signed-in user call Foundry + Search with DefaultAzureCredential ----
USER_OBJECT_ID=$(az ad signed-in-user show --query id -o tsv)
FOUNDRY_ID=$(az cognitiveservices account show -n "$FOUNDRY_NAME" -g "$RG" --query id -o tsv)
SEARCH_ID=$(az search service show -n "$SEARCH_NAME" -g "$RG" --query id -o tsv)

echo "==> Granting 'Cognitive Services User' on Foundry to your account"
az role assignment create \
  --assignee "$USER_OBJECT_ID" \
  --role "Cognitive Services User" \
  --scope "$FOUNDRY_ID" -o none

echo "==> Granting 'Search Index Data Contributor' + 'Search Service Contributor' on Search to your account"
az role assignment create \
  --assignee "$USER_OBJECT_ID" \
  --role "Search Index Data Contributor" \
  --scope "$SEARCH_ID" -o none
az role assignment create \
  --assignee "$USER_OBJECT_ID" \
  --role "Search Service Contributor" \
  --scope "$SEARCH_ID" -o none

# ---- Write out .env for the demo code ----------------------------------
FOUNDRY_ENDPOINT="https://${FOUNDRY_NAME}.services.ai.azure.com/api/projects/agent-demo-project"
SEARCH_ENDPOINT="https://${SEARCH_NAME}.search.windows.net"
APPI_CONNSTRING=$(az monitor app-insights component show -a "$APPINSIGHTS_NAME" -g "$RG" --query connectionString -o tsv)

cat > .env <<EOF
RESOURCE_GROUP=$RG
FOUNDRY_ENDPOINT=$FOUNDRY_ENDPOINT
MODEL_DEPLOYMENT_NAME=$MODEL_DEPLOYMENT_NAME
SEARCH_ENDPOINT=$SEARCH_ENDPOINT
SEARCH_SERVICE_NAME=$SEARCH_NAME
FUNCTION_APP_NAME=$FUNCTION_NAME
STORAGE_ACCOUNT_NAME=$STORAGE_NAME
APPLICATIONINSIGHTS_CONNECTION_STRING=$APPI_CONNSTRING
EOF

echo ""
echo "=================================================================="
echo " Done. Resource group: $RG"
echo " Config written to: $(pwd)/.env"
echo " Run 'az login' once per shell session, then the demo scripts pick"
echo " up credentials automatically via DefaultAzureCredential()."
echo "=================================================================="
