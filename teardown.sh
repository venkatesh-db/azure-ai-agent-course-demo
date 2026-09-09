#!/usr/bin/env bash
# Deletes the entire demo resource group created by setup.sh.
# This is DESTRUCTIVE and irreversible for anything in that group.
set -euo pipefail

RG="rg-ai-agent-demo"

read -p "This will permanently delete resource group '$RG' and everything in it. Type the RG name to confirm: " CONFIRM
if [ "$CONFIRM" != "$RG" ]; then
  echo "Confirmation did not match. Aborting."
  exit 1
fi

az group delete --name "$RG" --yes --no-wait
echo "Deletion of '$RG' started (running in background on Azure)."
