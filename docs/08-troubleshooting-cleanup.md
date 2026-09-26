# 8. 問題解決と後片付け

この章の調査手順は、第2章のWeb App、第4章のManual Job、第5章のKEDA Event Jobに適用できます。

リソース変更・権限付与・後片付けは管理者向けです。エンドユーザーは[第6章](./06-enduser-job-execution-process.md)に従って自分の実行を確認し、管理操作が必要な問題は管理者へ依頼してください。

## 問題調査の順番

1. Azure CLI が正しいサブスクリプションを向いているか
2. Azure リソースの provisioning state
3. Container Apps の System log
4. Job execution status
5. コンテナーの Console log
6. Managed Identity の RBAC
7. Private Endpoint と Private DNS
8. KEDA scale rule とイベント源

## `AuthorizationFailed`

現在のユーザーに、要求した操作を対象スコープで行う権限がありません。まずサブスクリプション、対象リソース、エラーに示された操作名を確認します。

```bash
az account show --output table
az role assignment list \
  --assignee "$(az ad signed-in-user show --query id --output tsv)" \
  --all \
  --output table
```

構築担当者がリソース作成・権限付与を行う場合は、対象 Resource Group の `Contributor` と、ロール割り当て用の `Role Based Access Control Administrator` など必要な権限を管理者へ依頼します。エンドユーザーの開始・履歴・ログ確認エラーには、これらの管理者権限を追加せず、[第6章の利用権限](./06-enduser-job-execution-process.md)と対象スコープを管理者が確認します。

## Storage の `AuthorizationPermissionMismatch`

管理プレーンで Storage Account を作れる権限と、Job が Storageデータを書き込む権限は別です。第4章のManual Jobには`Storage Blob Data Contributor`、第5章のKEDA用Managed Identityには`Storage Queue Data Contributor`と`Storage Blob Data Contributor`が必要です。割り当て後、反映に数分かかる場合があります。

```bash
STORAGE_ID=$(az storage account show \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query id --output tsv)

az role assignment list \
  --scope "$STORAGE_ID" \
  --query '[].{principal:principalId,role:roleDefinitionName}' \
  --output table
```

第4章のJobへBlob権限を再設定する場合:

```bash
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
  --query '{publicNetworkAccess:publicNetworkAccess,defaultAction:networkRuleSet.defaultAction}' \
  --output yaml

az network private-endpoint list \
  --resource-group "$RESOURCE_GROUP" \
  --query '[].{name:name,group:privateLinkServiceConnections[0].groupIds[0],connection:privateLinkServiceConnections[0].privateLinkServiceConnectionState.status}' \
  --output table
```

この教材では`publicNetworkAccess: Disabled`が正常です。第4章では`blob`、第5章では`queue`のPrivate Endpointが`Approved`であることを確認します。

DNS zone groupも確認します。

```bash
az network private-endpoint dns-zone-group show \
  --name "$STORAGE_PRIVATE_DNS_GROUP" \
  --endpoint-name "$STORAGE_PRIVATE_ENDPOINT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --output yaml

az network private-endpoint dns-zone-group show \
  --name "$QUEUE_PRIVATE_DNS_GROUP" \
  --endpoint-name "$QUEUE_PRIVATE_ENDPOINT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --output yaml
```

Blobには`privatelink.blob.core.windows.net`、Queueには`privatelink.queue.core.windows.net`が必要です。

Job のログに名前解決や接続timeoutが出る場合は、Container Apps EnvironmentがVNet統合されているか確認します。

```bash
az containerapp env show \
  --name "$CONTAINERAPPS_ENVIRONMENT" \
  --resource-group "$RESOURCE_GROUP" \
  --query properties.vnetConfiguration.infrastructureSubnetId \
  --output tsv
```

空の場合、そのEnvironmentはVNet未統合です。[通常の Container App 構築](./02-container-app.md#step-4-vnet-と専用-subnet-を作る)のStep 4からAppとEnvironmentを作り直します。

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

KEDA Jobの場合は、ユーザー割り当てManaged Identityとregistry設定を確認します。

```bash
az containerapp job identity show \
  --name "$KEDA_JOB_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --output yaml

az containerapp job registry list \
  --name "$KEDA_JOB_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --output table
```

ACRがABAC repository permissionsモードの場合は、`AcrPull`ではなく`Container Registry Repository Reader`が必要です。

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

## KEDA Event Jobが起動しない

まずscale ruleを確認します。

```bash
az containerapp job show \
  --name "$KEDA_JOB_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query properties.configuration.eventTriggerConfig.scale \
  --output yaml
```

次を確認します。

- `minExecutions`が`0`でも、Queueにメッセージがあれば起動する
- `maxExecutions`が`20`
- rule typeが`azure-queue`
- metadataのStorage Account名、Queue名、`queueLength=1`が正しい
- rule identityがKEDA用Managed IdentityのResource IDである

次にIdentityとQueue接続を確認します。

```bash
KEDA_PRINCIPAL_ID=$(az identity show \
  --name "$KEDA_IDENTITY_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query principalId --output tsv)

az role assignment list \
  --assignee "$KEDA_PRINCIPAL_ID" \
  --query '[].{role:roleDefinitionName,scope:scope}' \
  --output table

az network private-endpoint show \
  --name "$QUEUE_PRIVATE_ENDPOINT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query 'privateLinkServiceConnections[0].privateLinkServiceConnectionState.status' \
  --output tsv
```

`Storage Queue Data Contributor`がStorageスコープにあり、Private Endpointが`Approved`であることを確認します。KEDAの認証エラーはEnvironmentのSystem logにも出ます。

```bash
az containerapp env logs show \
  --name "$CONTAINERAPPS_ENVIRONMENT" \
  --resource-group "$RESOURCE_GROUP" \
  --tail 100
```

## KEDA Jobが20個同時に`Running`にならない

`maxExecutions=20`は上限であり、20個の同時配置を保証する予約値ではありません。次を切り分けます。

1. Seederログに20件の`message_enqueued`と`seed_completed`がある
2. `queueLength=1`である
3. Workerの`PROCESS_SECONDS=120`により観測時間が確保されている
4. Executionが順次`Succeeded`へ変わっていないか
5. EnvironmentのSystem logにクォータや容量エラーがないか

```bash
az containerapp job execution list \
  --name "$KEDA_JOB_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query '{running:length([?properties.status==`Running`]),succeeded:length([?properties.status==`Succeeded`]),failed:length([?properties.status==`Failed`]),total:length(@)}' \
  --output table
```

一瞬の`Running`数が20未満でも、最終的に今回の20 Executionが`Succeeded`になれば全件処理されています。同時数が継続して制限される場合はContainer Appsのクォータと利用可能容量を確認します。

## KEDA Jobが重複処理したように見える

Queueメッセージはat-least-onceで配信されるため、障害やvisibility timeout超過時に再配信される可能性があります。この教材は`batch_id/task_id`から決まるBlobパスへ上書き保存し、結果を冪等にしています。

`VISIBILITY_TIMEOUT`は`PROCESS_SECONDS`と`replica-timeout`より十分長くしてください。また、処理完了前にQueueメッセージを削除しないでください。

## Replica が見つからない

完了後にJob podがクリーンアップされるとReplicaを取得できない場合があります。Execution historyとLog Analyticsに保存されたログを使います。

## Job停止後も再実行されたように見える

Manual Jobでは`replica-retry-limit`を確認します。

```bash
az containerapp job show \
  --name "$JOB_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query properties.configuration.replicaRetryLimit \
  --output tsv
```

Event JobではQueueに未削除メッセージが残る限り、KEDAが新しいExecutionを開始できます。停止操作だけではイベント源は空になりません。

## 後片付け

最も確実なのは、この教材専用Resource Groupの一括削除です。削除対象を必ず確認します。

```bash
source scripts/set-env.sh
az resource list \
  --resource-group "$RESOURCE_GROUP" \
  --query '[].{name:name,type:type,location:location}' \
  --output table
```

`RESOURCE_GROUP`がこの教材専用であることを確認してから削除します。この操作は元に戻せません。

```bash
az group delete \
  --name "$RESOURCE_GROUP" \
  --yes
```

削除完了を確認します。

```bash
az group exists --name "$RESOURCE_GROUP"
```

`false`なら完了です。ローカルの一時結果も不要なら削除します。

```bash
rm -f /tmp/ca101-sim-job-*.json
```
