# 3. Container Apps Jobs の基本動作

## 3-1. Job のライフサイクル

Job は実行設定を保持する定義です。Job を起動するたびに新しい Execution ができます。

```text
Job 定義
  +-- Execution A: Running -> Succeeded
  +-- Execution B: Running -> Failed
  +-- Execution C: Running -> 停止
```

Job を停止する操作では、Job 定義ではなく対象 Execution を指定します。したがって、停止後も同じ Job を再実行できます。

## 3-2. 3種類のトリガー

| Trigger | 開始条件 | 代表例 |
|---|---|---|
| Manual | CLI、Portal、REST APIから開始 | 手動シミュレーション、移行処理 |
| Schedule | 5フィールドのcron式。評価はUTC | 夜間集計、定期バックアップ |
| Event | KEDA scaler がQueueなどを監視 | メッセージ単位の画像変換 |

この教材は Manual Job を使います。処理の開始と停止を自分で制御できるため、Execution の動きを理解しやすいからです。

## 3-3. 必須設定

| CLI 引数 | この教材 | 意味 |
|---|---:|---|
| `--replica-timeout` | 600 | 1 Replica が実行できる最大秒数 |
| `--replica-retry-limit` | 0 | 失敗後の再試行回数。Kill 実習を明確にするため0 |
| `--parallelism` | 1 | 1 Execution 内で同時実行する Replica 数 |
| `--replica-completion-count` | 1 | Execution 成功に必要な正常終了 Replica 数 |

`replica-completion-count` は `parallelism` 以下である必要があります。最初は両方 `1` にし、1 Execution と1 Replicaの関係を観察します。

## 3-4. 成功と失敗

- コンテナーが終了コード `0` で終わると正常終了として扱われます。
- 非ゼロで終わると失敗し、retry limit が残っていれば再試行されます。
- timeout を超えると処理は終了させられます。
- `az containerapp job stop` は指定した実行中 Execution を停止します。

アプリケーションは終了時に結果を確定保存し、再実行しても重複や破損が起きないよう設計する必要があります。この性質を「冪等性」と呼びます。

## 3-5. 状態、ログ、結果を分けて見る

| 観測対象 | 分かること | 主な方法 |
|---|---|---|
| Execution history | Running、Succeeded、Failed など管理面の状態 | `az containerapp job execution list` |
| Console log | 何%進んだか、アプリ内エラー | `az containerapp job logs show` |
| Blob result | 閉域 Storage へのアップロードが成功したか | `result_uploaded` / `checkpoint_uploaded` の Console log |

停止確認を状態表示だけに依存してはいけません。この教材では「Execution が動いていない」「`simulation_completed` と `result_uploaded` がない」「停止タイミングに余裕があれば `checkpoint_uploaded` がある」ことを確認します。

## 3-6. 組み込み環境変数

Container Apps Jobs は次の値をコンテナーへ自動設定します。

- `CONTAINER_APP_JOB_NAME`: Job 名
- `CONTAINER_APP_JOB_EXECUTION_NAME`: Execution 名
- `CONTAINER_APP_JOB_REPLICA_NAME`: Job Replica 名

サンプルはこれらをログと結果JSONに記録します。Azure CLI の Execution history と Console log を同じ Execution 名で照合できます。

次は [4. 必須シミュレーション実習](./04-simulation-lab.md)へ進みます。
