import json
import os
import sys
import time
from datetime import datetime, timezone

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.storage.queue import QueueClient


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def log(event, **fields):
    print(json.dumps({"timestamp": utc_now(), "event": event, **fields}), flush=True)


def create_clients():
    credential = DefaultAzureCredential()
    queue_client = QueueClient(
        account_url=os.environ["AZURE_STORAGE_QUEUE_URL"],
        queue_name=os.environ["QUEUE_NAME"],
        credential=credential,
    )
    blob_service = BlobServiceClient(
        account_url=os.environ["AZURE_STORAGE_ACCOUNT_URL"],
        credential=credential,
    )
    return queue_client, blob_service


def seed(queue_client):
    message_count = int(os.getenv("MESSAGE_COUNT", "20"))
    batch_id = os.getenv("BATCH_ID", f"batch-{int(time.time())}")

    for task_number in range(1, message_count + 1):
        task = {"batch_id": batch_id, "task_id": f"task-{task_number:02d}"}
        queue_client.send_message(json.dumps(task))
        log("message_enqueued", **task)

    log("seed_completed", batch_id=batch_id, message_count=message_count)


def process_one(queue_client, blob_service):
    visibility_timeout = int(os.getenv("VISIBILITY_TIMEOUT", "300"))
    process_seconds = float(os.getenv("PROCESS_SECONDS", "60"))
    messages = queue_client.receive_messages(
        messages_per_page=1,
        visibility_timeout=visibility_timeout,
    )
    message = next(iter(messages), None)
    if message is None:
        log("no_message")
        return

    task = json.loads(message.content)
    execution_name = os.getenv("CONTAINER_APP_JOB_EXECUTION_NAME", "local-execution")
    replica_name = os.getenv("CONTAINER_APP_JOB_REPLICA_NAME", "local-replica")
    log(
        "task_started",
        execution_name=execution_name,
        replica_name=replica_name,
        **task,
    )

    time.sleep(process_seconds)
    result = {
        "status": "succeeded",
        "completed_at": utc_now(),
        "execution_name": execution_name,
        "replica_name": replica_name,
        **task,
    }
    blob_name = f"keda-results/{task['batch_id']}/{task['task_id']}.json"
    payload = json.dumps(result, indent=2).encode("utf-8")
    blob_service.get_blob_client(
        os.environ["RESULT_CONTAINER"], blob_name
    ).upload_blob(
        payload,
        overwrite=True,
        content_settings=ContentSettings(content_type="application/json"),
    )
    log("result_uploaded", blob_name=blob_name, **task)

    queue_client.delete_message(message)
    log("task_completed", execution_name=execution_name, **task)


def main():
    queue_client, blob_service = create_clients()
    run_mode = os.getenv("RUN_MODE", "worker")
    if run_mode == "seed":
        seed(queue_client)
    elif run_mode == "worker":
        process_one(queue_client, blob_service)
    else:
        raise ValueError(f"Unsupported RUN_MODE: {run_mode}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        log("job_failed", error_type=type(error).__name__, error=str(error))
        sys.exit(1)