# 2. 通常の Container App 構築

この章では、Container Apps Environment と HTTP App を作り、ブラウザーアクセス、ログ、Revision、スケール設定を確認します。

## Step 1. 変数とログインを確認する

```bash
cd /home/hikurais/containerapps-101
source scripts/set-env.sh
az account show --query '{subscription:name, id:id, tenant:tenantId}' --output table
```

想定外のサブスクリプションが表示された場合は、先へ進まず `az account set --subscription "..."` で選び直します。

## Step 2. Azure CLI を準備する

```bash
az upgrade
az config set extension.dynamic_install_allow_preview=true
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
az provider register --namespace Microsoft.Network
az provider register --namespace Microsoft.Storage
az provider show --namespace Microsoft.App --query registrationState --output tsv
```

最後が `Registered` になることを確認します。登録には数分かかる場合があります。

## Step 3. Resource Group を作る

```bash
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output table
```

以降のリソースをこの箱へまとめるため、最後に Resource Group を削除すれば一括で後片付けできます。

## Step 4. VNet と専用 Subnet を作る

Container Apps Environment と Storage Private Endpoint を同じ VNet に配置します。Container Apps 用 Subnet と Private Endpoint 用 Subnet は分離します。

```bash
az network vnet create \
  --name "$VNET_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --address-prefixes "$VNET_ADDRESS_PREFIX" \
  --output table

CONTAINERAPPS_SUBNET_ID=$(az network vnet subnet create \
  --name "$CONTAINERAPPS_SUBNET_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --vnet-name "$VNET_NAME" \
  --address-prefixes "$CONTAINERAPPS_SUBNET_PREFIX" \
  --delegations Microsoft.App/environments \
  --query id --output tsv)

PRIVATE_ENDPOINT_SUBNET_ID=$(az network vnet subnet create \
  --name "$PRIVATE_ENDPOINT_SUBNET_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --vnet-name "$VNET_NAME" \
  --address-prefixes "$PRIVATE_ENDPOINT_SUBNET_PREFIX" \
  --disable-private-endpoint-network-policies true \
  --query id --output tsv)
```

Container Apps 用 Subnet は Environment 専用で、`Microsoft.App/environments` へ委任します。`/27` は workload profiles Environment の最小サイズです。本番用途では将来のスケールを考慮して、より大きな範囲を検討してください。

## Step 4A. Log Analytics workspace を作る

```bash
az monitor log-analytics workspace create \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$LOG_ANALYTICS_WORKSPACE" \
  --location "$LOCATION" \
  --output table
```

Environment 作成時だけ使う workspace ID と共有キーをシェル変数へ読み込みます。キーをファイルへ書いたり、画面へ表示したりしないでください。

```bash
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
  return 1 2>/dev/null || exit 1
fi
```

Step 4 と Step 5 は同じシェルで続けて実行してください。上記の変数は `export` していないため、コマンドを別の `.sh` ファイルへ移して `./ファイル名.sh` で実行すると、そのスクリプトからは参照できません。

## Step 5. Container Apps Environment を作る

既存の Container Apps Environment に VNet を後付けすることはできません。この章を以前の手順で実行済みの場合は、Container App と Environment を削除してから作り直します。Log Analytics workspace は削除不要です。

```bash
az containerapp delete \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --yes

az containerapp env delete \
  --name "$CONTAINERAPPS_ENVIRONMENT" \
  --resource-group "$RESOURCE_GROUP" \
  --yes
```

新規に実習している場合、上記の削除コマンドは実行しません。

```bash
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
```

Environment の作成には数分かかります。この Environment は VNet 統合されていますが、Web App のブラウザー実習を維持するため internal-only にはしません。Storage への通信は、後の章で Private Endpoint に閉じます。成功したら状態を確認します。

```bash
az containerapp env show \
  --name "$CONTAINERAPPS_ENVIRONMENT" \
  --resource-group "$RESOURCE_GROUP" \
  --query '{name:name, state:properties.provisioningState, location:location}' \
  --output table
```

## Step 6. HTTP App を作る

Microsoft の公開サンプルイメージを使用します。

```bash
az containerapp create \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$CONTAINERAPPS_ENVIRONMENT" \
  --image mcr.microsoft.com/k8se/quickstart:latest \
  --ingress external \
  --target-port 80 \
  --min-replicas 0 \
  --max-replicas 3 \
  --cpu 0.25 \
  --memory 0.5Gi \
  --output table
```

`external` はインターネットから到達可能な Ingress、`target-port 80` はコンテナーが待ち受けるポートです。

## Step 7. App へアクセスする

```bash
APP_FQDN=$(az containerapp show \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query properties.configuration.ingress.fqdn --output tsv)

echo "https://$APP_FQDN"
```

表示された `https://...` の URL をブラウザーのアドレスバーへ入力して開きます。`Welcome to Azure Container Apps` のサンプルページが表示されれば成功です。

ブラウザーを使わず、ターミナルから確認する場合は次のコマンドを実行します。

```bash
curl --fail --show-error --silent "https://$APP_FQDN" | head
```

HTML が返れば、ターミナルからの確認も成功です。最初のアクセスでは Scale from Zero のため、ブラウザーの表示や応答に数秒かかる場合があります。

## Step 8. Revision と Replica を確認する

```bash
az containerapp revision list \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query '[].{revision:name, active:properties.active, replicas:properties.replicas, health:properties.healthState}' \
  --output table
```

アクセス直後に Replica を確認します。

```bash
REVISION_NAME=$(az containerapp revision list \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query '[?properties.active].name | [0]' --output tsv)

az containerapp replica list \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --revision "$REVISION_NAME" \
  --output table
```

## Step 9. ログを確認する

System log:

```bash
az containerapp logs show \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --type system \
  --tail 50
```

Console log:

```bash
az containerapp logs show \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --type console \
  --tail 50
```

`--follow` を付けるとリアルタイム表示になります。終了するときは `Ctrl+C` を押します。

## Step 10. 設定変更で新しい Revision を作る

環境変数はコンテナー起動時の設定です。この変更により新しい Revision が作られます。

```bash
az containerapp update \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --set-env-vars LESSON=revision-2 \
  --output table

az containerapp revision list \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query '[].{revision:name, created:properties.createdTime, active:properties.active}' \
  --output table
```

既定の Single revision mode では、新しい Revision が準備できると古い Revision は非アクティブになります。

## Step 11. スケール設定を確認する

```bash
az containerapp show \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query 'properties.template.scale' \
  --output yaml
```

この実習では最小 `0`、最大 `3` です。これは常に3台動かす意味ではなく、要求に応じて0から3 Replicaの範囲で調整する意味です。

次は [3. Container Apps Jobs の基本](./03-jobs-basics.md)へ進みます。Markdown プレビューではリンクをクリックし、ソースの編集画面では `Ctrl` キーを押しながらクリックして開きます。Environment と App は削除せず、そのまま使います。
