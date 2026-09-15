#!/bin/bash

CONTAINERAPPS_SUBNET_ID=$(az network vnet subnet show \
  --name "$CONTAINERAPPS_SUBNET_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --vnet-name "$VNET_NAME" \
  --query id --output tsv)

LOG_ANALYTICS_ID=$(az monitor log-analytics workspace show \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$LOG_ANALYTICS_WORKSPACE" \
  --query customerId --output tsv)

LOG_ANALYTICS_KEY=$(az monitor log-analytics workspace get-shared-keys \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$LOG_ANALYTICS_WORKSPACE" \
  --query primarySharedKey --output tsv)

if [[ -z "$LOG_ANALYTICS_ID" || -z "$LOG_ANALYTICS_KEY" ]]; then
  echo "Log Analytics workspace ID または共有キーを取得できませんでした。" >&2
  exit 1
fi

az containerapp env create \
  --name "$CONTAINERAPPS_ENVIRONMENT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --infrastructure-subnet-resource-id "$CONTAINERAPPS_SUBNET_ID" \
  --logs-destination log-analytics \
  --logs-workspace-id "$LOG_ANALYTICS_ID" \
  --logs-workspace-key "$LOG_ANALYTICS_KEY" \
  --output table

unset LOG_ANALYTICS_KEY
