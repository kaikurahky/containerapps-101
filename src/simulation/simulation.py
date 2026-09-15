import json
import math
import os
import random
import signal
import sys
import time
from datetime import datetime, timezone

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings


stop_requested = False


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def log(event, **fields):
    message = {"timestamp": utc_now(), "event": event, **fields}
    print(json.dumps(message, ensure_ascii=True), flush=True)


def request_stop(signum, _frame):
    global stop_requested
    stop_requested = True
    log("termination_signal_received", signal=signum)


def upload_json(blob_service, container_name, blob_name, document):
    payload = json.dumps(document, indent=2, ensure_ascii=True).encode("utf-8")
    blob_service.get_blob_client(container_name, blob_name).upload_blob(
        payload,
        overwrite=True,
        content_settings=ContentSettings(content_type="application/json"),
    )


def main():
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    account_url = os.environ["AZURE_STORAGE_ACCOUNT_URL"]
    container_name = os.getenv("RESULT_CONTAINER", "simulation-results")
    steps = int(os.getenv("SIMULATION_STEPS", "24"))
    step_seconds = float(os.getenv("STEP_SECONDS", "5"))
    samples_per_step = int(os.getenv("SAMPLES_PER_STEP", "100000"))
    job_name = os.getenv("CONTAINER_APP_JOB_NAME", "local-job")
    execution_name = os.getenv("CONTAINER_APP_JOB_EXECUTION_NAME", f"local-{int(time.time())}")
    replica_name = os.getenv("CONTAINER_APP_JOB_REPLICA_NAME", "local-replica")

    credential = DefaultAzureCredential()
    blob_service = BlobServiceClient(account_url=account_url, credential=credential)
    random_generator = random.Random(execution_name)
    started_at = utc_now()
    inside_circle = 0
    completed_samples = 0

    log(
        "simulation_started",
        job_name=job_name,
        execution_name=execution_name,
        replica_name=replica_name,
        steps=steps,
        samples_per_step=samples_per_step,
    )

    for step in range(1, steps + 1):
        if stop_requested:
            checkpoint = {
                "status": "stopped",
                "job_name": job_name,
                "execution_name": execution_name,
                "replica_name": replica_name,
                "started_at": started_at,
                "stopped_at": utc_now(),
                "completed_steps": step - 1,
                "requested_steps": steps,
                "completed_samples": completed_samples,
                "pi_estimate": 4 * inside_circle / completed_samples if completed_samples else None,
            }
            try:
                upload_json(
                    blob_service,
                    container_name,
                    f"checkpoints/{execution_name}.json",
                    checkpoint,
                )
                log("checkpoint_uploaded", execution_name=execution_name)
            except Exception as error:
                log("checkpoint_upload_failed", error=str(error))
            return 143

        for _ in range(samples_per_step):
            x_coordinate = random_generator.random()
            y_coordinate = random_generator.random()
            if x_coordinate * x_coordinate + y_coordinate * y_coordinate <= 1:
                inside_circle += 1

        completed_samples += samples_per_step
        pi_estimate = 4 * inside_circle / completed_samples
        log(
            "progress",
            execution_name=execution_name,
            step=step,
            total_steps=steps,
            percent=round(step * 100 / steps, 1),
            pi_estimate=pi_estimate,
            absolute_error=abs(math.pi - pi_estimate),
        )
        time.sleep(step_seconds)

    result = {
        "status": "succeeded",
        "job_name": job_name,
        "execution_name": execution_name,
        "replica_name": replica_name,
        "started_at": started_at,
        "completed_at": utc_now(),
        "steps": steps,
        "samples": completed_samples,
        "pi_estimate": 4 * inside_circle / completed_samples,
        "absolute_error": abs(math.pi - 4 * inside_circle / completed_samples),
    }
    log("simulation_completed", **result)
    upload_json(blob_service, container_name, f"results/{execution_name}.json", result)
    log("result_uploaded", blob_name=f"results/{execution_name}.json")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        log("simulation_failed", error_type=type(error).__name__, error=str(error))
        raise
