#!/usr/bin/env bash

set -uo pipefail

missing=0

for command_name in az curl python3 sha256sum; do
  if command -v "$command_name" >/dev/null 2>&1; then
    printf '[OK] %s: %s\n' "$command_name" "$(command -v "$command_name")"
  else
    printf '[NG] %s が見つかりません。\n' "$command_name" >&2
    missing=1
  fi
done

if ! command -v az >/dev/null 2>&1; then
  exit 1
fi

printf '\nAzure CLI version:\n'
az version --query '"azure-cli"' --output tsv

if az account show >/dev/null 2>&1; then
  printf '\nAzure login: OK\n'
  az account show --query '{subscription:name, id:id, tenant:tenantId}' --output table
else
  printf '\nAzure login: NG。az login --use-device-code を実行してください。\n' >&2
  missing=1
fi

if [[ "$missing" -ne 0 ]]; then
  exit 1
fi

printf '\n事前確認に成功しました。\n'