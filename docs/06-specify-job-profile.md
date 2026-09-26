# 7. ジョブプロファイルの指定と留意点

この章では、エンドユーザーからよく聞かれる5つの質問を通して、Container Apps Jobsの計算資源の指定方法と制約を整理します。既存Jobの投入・確認・取消と必要権限は[第6章](./06-enduser-job-execution-process.md)を参照してください。

ここでいう「ジョブプロファイル」は、JobのCPU・メモリ・並列度と、実行基盤のワークロードプロファイルを合わせた説明上の呼び方です。Azureの設定としては別の項目です。本章を読むために、リソースの作成や変更を行う必要はありません。

## 最初に区別する単位

| 単位 | 意味 |
|---|---|
| Environment | AppやJobが動く環境。ネットワークやワークロードプロファイルを管理する |
| ワークロードプロファイル | 計算基盤の種類・サイズ。ConsumptionやDedicatedなど |
| Job | イメージ、CPU・メモリ、トリガーなどを保存した定義 |
| Execution | Jobを1回実行したもの |
| Replica | Execution内で動くコンテナー群の実行インスタンス。VMとは異なる |
| ノード | Replicaを配置する基盤側の計算ノード |

この教材は1 Replicaに1コンテナー、1 Executionに1 Replicaの構成です。以下の「1実行あたりのCPU」は、この前提で説明しています。

## 質問1. Seederはジョブスケジューラーのキューか？

**Seederはキューではなく、キューへ作業を投入するプログラムです。** 第5章では、この投入プログラム自体をManual Jobとして実行します。

| 要素 | 教材での役割 |
|---|---|
| Seeder | 20件の作業メッセージをQueueへ送る |
| Azure Storage Queue | 処理待ちのメッセージを保持する |
| KEDA | Queueの量とスケール設定に基づき、Executionの起動数を判断する |
| Container Apps | ExecutionのReplicaを計算基盤へ配置する |
| Worker | メッセージを1件取得し、処理・Blob保存後にメッセージを削除する |

キューに相当するのはAzure Storage Queueです。ただし、Slurmなどのジョブスケジューラーのように、優先順位、ノード予約、複数ノードの一括割り当てまで行う仕組みではありません。

Seederの成功は「投入処理の完了」であり、Workerによる全タスクの処理完了ではありません。Workerの状態とタスクごとの成果物を別に確認します。

## 質問2. 実行VMはどこで指定するか？種類を変更できるか？

**今回の教材では、実行するVMを直接指定していません。** [第2章](./02-container-app.md)で作ったEnvironmentをJobの`--environment`で指定し、既定のConsumptionプロファイルを使います。実行基盤の選択・配置はAzureが管理します。

計算基盤の容量や種類を選びたい場合は、管理者がEnvironmentにDedicatedワークロードプロファイルを追加し、Jobの`--workload-profile-name`でそのプロファイル名を指定します。この引数はVM SKUではなく、Environment内に作成したプロファイルの名前です。

### D/EプロファイルとVM SKUは別物

| 指定内容 | DedicatedのD/Eプロファイルでの扱い |
|---|---|
| 汎用・メモリ重視の分類 | D系・E系から選択可能 |
| 基盤ノードのCPU・メモリ容量 | D4、D8、D16、D32、E4、E8、E16、E32など、公開されたサイズから選択 |
| VM世代のv5・v6・v7 | 指定不可 |
| `Standard_D4as_v7`のような完全なVM SKU | 指定不可 |
| CPUメーカー・モデル | 指定不可 |
| 自分で作った既存VMを実行先にする | 不可 |

例えばD4は4 vCPU・16 GiB、E4は4 vCPU・32 GiBのノード単位のプロファイルです。**D4を選んでも、`Standard_D4as_v7`で動くとは保証されません。** 「ノードの種類を選べる」とは、Container Appsが公開するプロファイルの種類・サイズを選べるという意味です。

ノードの公称容量の一部はランタイムが使うため、その全量をJobに割り当てられるわけではありません。また、同じプロファイルのノードを複数のAppやJobで共有できます。Dedicatedを選んでも、特定のJobが1台を専有する保証にはなりません。

CPU世代や完全なVM SKUの指定が要件なら、Azure BatchやAzure CycleCloudとSlurmなど、VMサイズを指定できる実行基盤を検討します。プロファイルの種類・提供リージョンは[公式一覧](https://learn.microsoft.com/azure/container-apps/workload-profiles-overview#dedicated-profile-details)で確認してください。

## 質問3. 1ジョブあたりのコア数はデフォルト何コアか？

**この教材では、Job作成時にCPU・メモリを明示指定しています。** 実行時に指定し直さないのは、Job定義に保存した値を使うためです。

| 対象 | コンテナーのCPU | メモリ | 1 ExecutionのReplica数 |
|---|---:|---:|---:|
| [第4章のシミュレーションJob](./04-simulation-lab.md) | 0.5 vCPU | 1 GiB | 1 |
| [第5章のKEDA Worker](./05-keda-autoscaling.md) | 0.5 vCPU | 1 GiB | 1 |
| 第5章のSeeder | 0.25 vCPU | 0.5 GiB | 1 |

作成コマンドでは`--cpu 0.5 --memory 1Gi`などを指定しています。これはContainer Apps Jobs全体で一律のデフォルトが0.5 vCPUという意味ではありません。新しいJobでも省略時の既定値に依存せず、CPU・メモリを明示してください。

0.5 vCPUは物理コアの半分を専有・固定する指定ではなく、コンテナーに割り当てる仮想CPU量です。複数コンテナーを含むReplicaでは、コンテナーごとのCPU・メモリを合計して考えます。

また、CPUを増やしてもプログラムが自動的に並列化されるわけではありません。第4章のサンプルは複数コアへ計算を分割する実装ではなく、第5章のWorkerは待機によって処理時間を模擬しているため、CPU増量による高速化を測る教材ではありません。

## 質問4. 実行に必要なVM台数・コア数を指定できるか？

**コンテナーのCPU・メモリとReplicaの並列数は指定できますが、Job単位で使うVM台数は指定できません。**

| 指定したいもの | 設定 | 注意点 |
|---|---|---|
| コンテナーあたりのCPU・メモリ | `--cpu`、`--memory` | プロファイルで許可された容量・組み合わせの範囲内 |
| 1 Execution内の並列Replica数 | `--parallelism` | VM台数ではない |
| Executionの成功に必要なReplica数 | `--replica-completion-count` | 並列度とは別。必要な全Replicaの成功を待つよう設計する |
| Event Jobのスケーリング | `minExecutions`、`maxExecutions`、スケールルール | ノード予約ではなくExecution数の制御 |
| Dedicated基盤のノード台数範囲 | プロファイルの最小・最大インスタンス数 | プロファイル全体の設定。個別Jobへの台数割り当てではない |

例えば、1コンテナー2 vCPUのReplicaを3個同時に動かす場合、合計のCPU要求量は6 vCPUです。しかし、3台のVMを使う意味ではなく、複数Replicaが同じノードへ配置される可能性があります。同じ処理を3回起動するだけでは計算の分割にならないため、入力の分担もアプリ側で設計します。

今回のWorkerが20 Execution同時に動くなら、各Executionは1 Replicaなので、合計要求量は10 vCPU・20 GiBです。**20 Executionは20 VMではありません。** また、`maxExecutions=20`は上限であり、20件の同時起動や資源確保を保証する予約値ではありません。クォータや利用可能容量も影響します。

### 実行時にサイズを選ばせたい場合

Manual Jobでは、開始時の実行テンプレートでCPU・メモリなどを上書きする方法があります。ただし、ワークロードプロファイルの選択や基盤ノードの台数設定とは別です。Event JobはQueueの任意のメッセージ項目を見て、CPU・メモリやプロファイルを自動変更する仕組みではありません。

一般のエンドユーザーには、管理者が用意した「小・中・大」などの許可済みサイズを受付APIで選ばせる運用が適しています。API側でJob定義や検証済み実行テンプレートへ対応付け、CPU・メモリ上限、並列数、費用を制限します。Event Jobならサイズ別のQueueとWorker Jobに分ける方法もあります。これらの受付・振り分け機能は現行教材には実装していません。

直接のJob開始権限は、CPUだけでなくイメージやコマンドなどの上書きにもつながるため、「サイズ選択だけを許可する権限」として配布しません。権限とManaged Identityの注意は[第6章](./06-enduser-job-execution-process.md)を参照してください。

## 質問5. 2ノードを使うMPI並列Jobは実行できるか？

**Container Apps Jobsには、指定した2ノードを確保してMPIを協調起動する標準の実行機構はありません。** `--parallelism 2`はその代わりにはなりません。

- 2 Replicaを別々のノードへ配置する保証がありません。
- 複数ノードの一括割り当て、MPI用ホスト一覧、全参加プロセスの起動調整は提供されません。
- JobsはIngressに対応せず、Replica間のMPI通信経路やRDMAを選択・構成するためのHPC向け機能も提供しません。

これは、コンテナー内でMPIライブラリを使うこと自体が一律に不可能という意味ではありません。単一コンテナー内で複数MPIプロセスを動かすことと、2台の計算ノードにまたがるMPI実行は別です。

| 要件 | 適した選択肢 |
|---|---|
| 独立した20件の作業をQueueに応じて並列処理する | 今回のContainer Apps JobsとKEDA |
| 指定した複数の計算ノードで1つのMPIタスクを動かす | Azure Batchのマルチインスタンスタスク |
| ノード数・CPU資源・パーティションを指定してMPIジョブを投入する | Azure CycleCloudとSlurm |

Azure Batchのマルチインスタンスタスクは計算ノード数を指定し、ノード間の準備・協調実行を行えます。CycleCloudとSlurmでは、管理者がVMサイズやネットワークを構成し、利用者はスケジューラーへ必要なノード・CPU資源を要求します。いずれもMPI実装、ノード間通信、必要ならRDMA対応VMなどの事前準備が必要です。

## 管理者へ伝える要件

サイズ変更や実行基盤の相談では、次を伝えると判断しやすくなります。

1. 独立タスクの並列処理か、ノード間通信が必要なMPI計算か。
2. 1タスクあたりのCPU・メモリ・実行時間と、アプリの並列化対応状況。
3. 同時に処理したいタスク数と、待機を許容できる時間。
4. CPUメーカー・世代・完全なVM SKU・RDMAなどの必須条件。
5. 入出力データの場所、アクセス権、想定費用の上限。

## 公式資料

- [Container Appsのワークロードプロファイル](https://learn.microsoft.com/azure/container-apps/workload-profiles-overview)
- [Container Apps Jobsの概念・設定・実行時上書き・制約](https://learn.microsoft.com/azure/container-apps/jobs)
- [Azure CLI: Container Apps Job](https://learn.microsoft.com/cli/azure/containerapp/job?view=azure-cli-latest)
- [Azure BatchのMPI・マルチインスタンスタスク](https://learn.microsoft.com/azure/batch/batch-mpi)
- [Azure CycleCloudの概要](https://learn.microsoft.com/azure/cyclecloud/overview?view=cyclecloud-8)

記載内容は2026年9月26日時点の公式仕様と教材のJob定義に基づきます。Dedicatedへの変更やMPI環境の構築・動作検証は本章では行いません。

次は [8. 問題解決と後片付け](./08-troubleshooting-cleanup.md)へ進みます。リソース変更・削除の手順は管理者向けです。