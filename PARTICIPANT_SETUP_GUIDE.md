# AI & Automation: Develop Production-Ready AI Agents on Azure
## Participant Environment Setup Guide

This guide gets your Azure environment ready **before** the workshop starts.
Complete it at least 24 hours in advance — a couple of steps (resource
provider registration, model quota) can take time to process and are not
things you want to be waiting on during class.

---

## 1. Prerequisites

- An Azure subscription with an active credit balance or billing method.
  Free-tier / trial subscriptions work but may hit quota limits — a pay-as-
  you-go or sponsored subscription is recommended.
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) installed
  (`az --version` to check).
- Python 3.10+ installed (`python3 --version` to check).
- `git` installed.
- A code editor (VS Code recommended).

## 2. Sign in

```bash
az login
```

This opens a browser window. Sign in with the Azure account you'll use for
the workshop. If you have multiple subscriptions, the CLI will ask you to
pick one — confirm it's the one you intend to use for this course.

Verify:

```bash
az account show --query "{user:user.name, subscription:name}" -o table
```

## 3. Register required resource providers (one-time, ~5-10 minutes)

New or lightly-used subscriptions are often not yet registered for the
services this course uses. Registering is free and non-destructive. Run
this now so it's ready by class time:

```bash
az provider register --namespace Microsoft.CognitiveServices
az provider register --namespace Microsoft.Search
az provider register --namespace Microsoft.Web
az provider register --namespace Microsoft.Insights
az provider register --namespace Microsoft.Storage
az provider register --namespace Microsoft.OperationalInsights
```

Check status (should say `Registered`, may take a few minutes):

```bash
az provider show -n Microsoft.CognitiveServices --query registrationState -o tsv
```

## 4. Run the environment setup script

Clone or download the workshop repository, then:

```bash
cd azure-agent-demo-setup
chmod +x setup.sh
./setup.sh
```

This provisions everything the labs need in a dedicated resource group
(`rg-ai-agent-demo`), so it's easy to identify and remove afterward:

| Resource | Purpose |
|---|---|
| Azure AI Foundry project + `gpt-5-mini` model deployment | Agent creation labs (Day 1–3) |
| `text-embedding-3-small` model deployment | RAG / vector search lab |
| Azure AI Search (Basic tier) | Enterprise knowledge / RAG lab |
| Storage account | Backing store for the Function App |
| Application Insights | Tracing / observability lab |
| Azure Function App (Linux, Python) | Tool-calling / automation lab |

The script also grants your account the specific Azure roles needed to run
everything with `az login`-based authentication — no API keys to manage or
lose track of.

**Expect this to take 5–10 minutes.** It prints progress as it goes.

### If it fails partway through

The script is safe to re-run — az CLI resource creation is idempotent for
most steps. Common first-run issues:

- **`MissingSubscriptionRegistration`** — you skipped step 3, or a provider
  is still finishing registration. Wait a few minutes and re-run.
- **`InsufficientResourcesAvailable`** for Azure AI Search — that region is
  temporarily out of capacity. Edit `SEARCH_NAME`'s region in `setup.sh`
  to `eastus` (or another nearby region) and re-run just that step.
- **Model deployment errors** (deprecated model / wrong SKU) — Azure's
  available models and SKUs change over time. Run
  `az cognitiveservices account list-models -l eastus2` to see current
  options and update `MODEL_NAME` / `MODEL_VERSION` / SKU in `setup.sh`
  accordingly.

If you get stuck, come to office hours or post in the workshop channel
with the exact error text — don't guess your way past an error, since a
misconfigured resource is harder to debug later than to fix now.

## 5. Verify your environment

```bash
cd day1
python3 -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements.txt
python3 lab1_verify_environment.py
```

You should see output ending in:

```
Response: environment ok
Latency: ... ms
Tokens: prompt=... completion=... total=...

Environment verified.
```

Each day has its own `requirements.txt` (`day1/`, `day2/`, `day3/`) —
install the new one when that day's labs begin:

```bash
cd ../day2 && pip install -r requirements.txt   # before Day 2
cd ../day3 && pip install -r requirements.txt   # before Day 3
```

**Day 2's Azure Function lab** (tool-calling via a real Azure Function)
needs the Azure Functions Core Tools CLI, which `setup.sh` does not
install:

```bash
brew tap azure/functions && brew install azure-functions-core-tools@4
```

If Homebrew refuses the tap as "untrusted," run
`brew trust --tap azure/functions` first — that's a one-time trust
confirmation for the official Microsoft tap, not an error.

If Lab 1 verification passed above, you're fully ready for Day 1.

## 6. What to bring / have open on the first day

- This terminal, already authenticated (`az login` sessions typically
  last several hours — re-run `az login` if it's been a while).
- The cloned workshop repository.
- Azure Portal (portal.azure.com) open in a browser tab, filtered to
  resource group `rg-ai-agent-demo`, so you can see what you built.

## 7. Cost expectations

Everything provisioned uses Basic/Consumption/pay-as-you-go tiers. Typical
usage across all 3 days of hands-on labs costs **under $5 USD** in API and
compute charges — trivial against most course credit allowances. If you
want to double-check, Azure Portal → Cost Management + Billing → Cost
analysis, filtered to `rg-ai-agent-demo`.

## 8. Cleaning up after the workshop

When the course is complete and you no longer need the environment:

```bash
cd azure-agent-demo-setup
./teardown.sh
```

This deletes the entire `rg-ai-agent-demo` resource group and everything
in it. It asks you to type the resource group name to confirm — this is
irreversible, so only run it once you're done with the material.

---

### Questions before the workshop?

Contact your workshop coordinator with:
- The exact error message (copy-paste, not a screenshot description)
- Output of `az account show`
- Which step in this guide you were on
