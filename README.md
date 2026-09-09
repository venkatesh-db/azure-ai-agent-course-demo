# AI Agent Demo — Azure Setup

Provisions everything needed to live-code the 3-day "AI & Automation:
Develop Production-Ready AI Agents on Azure" course demos.

## What gets created (resource group `rg-ai-agent-demo`)

| Resource | Used for |
|---|---|
| Azure AI Foundry (AIServices) + `gpt-4o-mini` deployment | Day 1 Module 2–3: agent creation, structured output |
| Azure AI Search (Basic) | Day 1 Module 4–5: RAG grounding demo |
| Storage account | Function App backing store |
| Function App (Consumption, Python 3.11) + managed identity | Day 2 Module 3: tool-as-Azure-Function demo |
| Application Insights | Day 3 Module 1: tracing demo |
| RBAC role assignments on your own user | so `DefaultAzureCredential()` works with zero keys in code |

## Run it

```bash
az login
cd azure-agent-demo-setup
chmod +x setup.sh teardown.sh
./setup.sh
```

Takes ~5-8 minutes (Search and Function App provisioning are the slow parts).
Writes a `.env` file with every endpoint/name the demo code needs — nothing
in it is a secret, since everything auths via your Azure CLI login.

## Cost

All Basic/Consumption/S0 tiers. A full demo day costs well under $5 in
API/compute usage — trivial against your ₹19,109 credit balance.

## Cleanup

```bash
./teardown.sh
```

Deletes the whole resource group. Requires typing the RG name to confirm.

## Known gotchas

- **Model region availability**: `gpt-4o-mini` isn't deployable in every
  region. If the deployment step fails, change `LOCATION` in `setup.sh` to
  `eastus`, `swedencentral`, or check current availability with:
  `az cognitiveservices account list-models --location <region>`
- **Quota**: new subscriptions sometimes start with 0 TPM quota for a model.
  If deployment succeeds but calls 429, request a quota increase in the
  Foundry portal (Quota tab) — usually auto-approved for small amounts.
- **Storage account name collisions**: names are globally unique; if the
  `$RANDOM` suffix collides, just re-run `setup.sh`.
