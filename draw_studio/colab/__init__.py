"""Host-side Colab client and standalone code uploaded to the GPU."""

from pathlib import Path

WORKER_SCRIPT = Path(__file__).with_name("worker.py")
