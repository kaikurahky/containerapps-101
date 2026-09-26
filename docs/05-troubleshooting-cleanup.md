# 5. 問題解決と後片付け

## 問題調査の順番

1. Azure CLI が正しいサブスクリプションを向いているか
2. Azure リソースの provisioning state
3. Container Apps の System log
4. Job execution status
5. コンテナーの Console log
6. Managed Identity の RBAC

## `AuthorizationFailed`

現在のユーザーにリソース作成またはロール割り当て権限がありません。

```bash
az account show --output table
az role assignment list \
  --assignee "$(az ad signed-in-user show --query id --output tsv)" \
  --all \
  --output table
```

管理者へ対象 Resource Group の `Contributor` と、ロール割り当て用の `Role Based Access Control Administrator` など必要な権限を依頼します。

## Storage の `AuthorizationPermissionMismatch`

管理プレーンで Storage Account を作れる権限と、Job が Blob データを書き込む権限は別です。Job の Managed Identity に、学習用 Storage Account スコープの `Storage Blob Data Contributor` があるか確認します。割り当て後、反映に数分かかる場合があります。

```bash
STORAGE_ID=$(az storage account show \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query id --output tsv)

az role assignment create \
  --assignee-object-id "$JOB_PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Storage Blob Data Contributor" \
  --scope "$STORAGE_ID"
```

## Storage の `The request may be blocked by network rules`

Storage Account の公開ネットワークが無効であることと、Private Endpoint 接続を確認します。

```bash
az storage account show \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query '{publicNetworkAccess:publicNetworkAccess, defaultAction:networkRuleSet.defaultAction}' \
  --output yaml

az network private-endpoint show \
  --name "$STORAGE_PRIVATE_ENDPOINT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query '{privateIp:customDnsConfigs[0].ipAddresses[0], connection:privateLinkServiceConnections[0].privateLinkServiceConnectionState.status}' \
  --output yaml

az network private-endpoint dns-zone-group show \
  --name "$STORAGE_PRIVATE_DNS_GROUP" \
  --endpoint-name "$STORAGE_PRIVATE_ENDPOINT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --output yaml
```

この教材では `publicNetworkAccess: Disabled` が正常です。Private Endpoint の `connection` が `Approved` で、DNS zone group に `privatelink.blob.core.windows.net` が設定されていることを確認します。

Job のログに名前解決や接続 timeout が出る場合は、Container Apps Environment が VNet 統合されているか確認します。

```bash
az containerapp env show \
  --name "$CONTAINERAPPS_ENVIRONMENT" \
  --resource-group "$RESOURCE_GROUP" \
  --query properties.vnetConfiguration.infrastructureSubnetId \
  --output tsv
```

空の場合、その Environment は VNet 未統合です。[通常の Container App 構築](./02-container-app.md#step-4-vnet-と専用-subnet-を作る) の Step 4 から App と Environment を作り直します。

## `ImagePullBackOff` またはイメージ取得失敗

```bash
az containerapp env logs show \
  --name "$CONTAINERAPPS_ENVIRONMENT" \
  --resource-group "$RESOURCE_GROUP" \
  --tail 100

az role assignment list \
  --assignee "$JOB_PRINCIPAL_ID" \
  --scope "$ACR_ID" \
  --output table

az containerapp job registry list \
  --name "$JOB_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --output table
```

ACRがABAC repository permissionsモードの場合は、`AcrPull` ではなく `Container Registry Repository Reader` が必要です。

## Job が `Failed` になる

```bash
az containerapp job execution list \
  --name "$JOB_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --output table

az containerapp job logs show \
  --name "$JOB_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --container simulation \
  --tail 100 \
  --format text
```

よくある原因は、Blob RBACの反映待ち、環境変数の誤り、timeout、Python例外です。

## Replica が見つからない

完了後にJob podがクリーンアップされるとReplicaを取得できない場合があります。Execution history と Log Analytics に保存されたログを使います。

## Job停止後も再実行されたように見える

`replica-retry-limit` が0か確認します。

```bash
az containerapp job show \
  --name "$JOB_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query properties.configuration.replicaRetryLimit \
  --output tsv
```

## 後片付け

最も確実なのは、この教材専用 Resource Group の一括削除です。削除対象を必ず確認します。

```bash
source scripts/set-env.sh
az resource list \
  --resource-group "$RESOURCE_GROUP" \
  --query '[].{name:name,type:type,location:location}' \
  --output table
```

`RESOURCE_GROUP` がこの教材専用であることを確認してから削除します。この操作は元に戻せません。

```bash
az group delete \
  --name "$RESOURCE_GROUP" \
  --yes
```

削除完了を確認します。

```bash
az group exists --name "$RESOURCE_GROUP"
```

`false` なら完了です。ローカルの一時結果も不要なら削除します。

```bash
rm -f /tmp/ca101-sim-job-*.json
```
