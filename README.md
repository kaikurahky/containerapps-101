# Azure Container Apps 101

Azure で Azure Container Apps と Container Apps Jobs を順番に理解するハンズオン教材になります。

## このハンズオンの内容

1. Environment、App、Revision、Replica、Job、Execution の違いを説明する
2. HTTP でアクセスできる Container App を作成して更新する
3. 手動起動する Container Apps Job を作成する
4. VNet と Private Endpoint で閉域化した Blob Storage へシミュレーション結果を保存する
5. 実行中の Job execution を停止し、停止状態と途中結果を確認する
6. 管理者の構築作業とエンドユーザーの投入・確認・取消操作を区別する
7. CPU, Replica, VMの違い、ワークロードプロファイルや制約を説明する
8. 学習用 Azure リソースをまとめて削除

## 構成

| 順序 | 教材 | 内容 | 目安 |
|---|---|---|---:|
| 1 | [基礎概念](docs/01-fundamentals.md) | 用語と全体像 | 30分 |
| 2 | [通常の Container App](docs/02-container-app.md) | 環境、Web App、Revision、ログ | 60分 |
| 3 | [Jobs の基本](docs/03-jobs-basics.md) | Job の種類と設定 | 30分 |
| 4 | [シミュレーション実行](docs/04-simulation-lab.md) | ACR、Storage、正常実行、Kill | 90分 |
| 5 | [KEDA オートスケール実行](docs/05-keda-autoscaling.md) | Queue、Event Job、スケール監視 | 60分 |
| 6 | [エンドユーザーのJob実行](docs/06-enduser-job-execution-process.md) | 必要権限、単一・スケーリングJobの投入・確認・取消 | 30分 |
| 7 | [ジョブプロファイルの指定と留意点](docs/07-specify-job-profile.md) | Seeder、CPU・並列度、VM SKU指定の制約、MPI | 20分 |
| 8 | [問題解決と後片付け](docs/08-troubleshooting-cleanup.md) | エラー調査と削除 | 20分 |

管理者が環境を構築済みの場合、エンドユーザーは第6章から参照してください。一般利用者向け受付APIは未実装のため、提供に必要な準備と、信頼済み利用者向けのCLI直接実行を分けて説明しています。以下のリソース作成・ロール割り当て権限は構築担当者向けです。

## 前提条件

- Ubuntu 22.04 または 24.04 を推奨
- Azure サブスクリプション
- リソース作成とロール割り当てが可能な権限
- Bash、`curl`、Python 3
- Azure CLI 2.60 以降を推奨
- VNet、Private Endpoint、Private DNS zone、ロール割り当てを作成できる権限
- Docker は任意です。イメージは ACR 上でビルドするため、ローカル Docker は不要です。

この教材では Storage の公開ネットワークアクセスを使用しません。Container Apps Environment を VNet 統合し、Job から Blob Storage へ Private Endpoint 経由で接続します。実行端末は VNet 外のままで構いません。Azure リソースの作成、Job の開始・停止、ログ確認は ARM 管理プレーンで行います。

Azure CLI が未導入の場合:

```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

このリポジトリのルートへ移動し、事前確認を実行します。

```bash
cd /home/hikurais/containerapps-101
chmod +x scripts/*.sh
./scripts/check-prerequisites.sh
```

## 最初の準備

Azure にログインします。SSH 接続中など、ブラウザーが同じ端末で開かない場合はデバイスコード方式を使います。

```bash
az login --use-device-code
az account list --output table
az account set --subscription "<使用するサブスクリプション名またはID>"
az account show --output table
```

実習用変数ファイルを作ります。これは `.gitignore` の対象です。

```bash
cp scripts/set-env.sh.example scripts/set-env.sh
source scripts/set-env.sh
```

値を確認します。

```bash
printf 'RESOURCE_GROUP=%s\nLOCATION=%s\nACR_NAME=%s\nSTORAGE_ACCOUNT=%s\n' \
  "$RESOURCE_GROUP" "$LOCATION" "$ACR_NAME" "$STORAGE_ACCOUNT"
```

以前の手順で VNet 未統合の Container Apps Environment を作成済みの場合は、[通常の Container App](docs/02-container-app.md#step-4-vnet-と専用-subnet-を作る) の Step 4 からやり直します。Environment には作成後に VNet を追加できないため、既存の App と Environment の再作成が必要です。

## 費用と注意

この実習では Container Apps、VNet、Storage Private Endpoint、Private DNS zone、ACR Basic、Storage、Log Analytics を作成します。Private Endpoint には時間単位とデータ処理量に応じた料金が発生します。短時間の学習でも無料とは限らないため、実習後は管理者が[後片付け](docs/08-troubleshooting-cleanup.md)を実施してください。エンドユーザーは共有リソースを削除しません。

コマンドは Bash 用です。`<...>` は自分の値へ置き換える表記です。一方、`$RESOURCE_GROUP` のような値は `set-env.sh` から読み込まれるため、そのまま実行します。

## 公式資料

- [Azure Container Apps overview](https://learn.microsoft.com/azure/container-apps/overview)
- [Jobs in Azure Container Apps](https://learn.microsoft.com/azure/container-apps/jobs)
- [Application logging](https://learn.microsoft.com/azure/container-apps/logging)
- [Azure Container Apps virtual networks](https://learn.microsoft.com/azure/container-apps/custom-virtual-networks)
- [Azure Private Endpoint DNS configuration](https://learn.microsoft.com/azure/private-link/private-endpoint-dns)
- [Azure CLI: az containerapp job](https://learn.microsoft.com/cli/azure/containerapp/job?view=azure-cli-latest)
