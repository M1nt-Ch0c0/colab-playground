#!/usr/bin/env python3
"""Start Draw Studio with python app.py or uvicorn app:app."""
import os

import uvicorn

from draw_studio.application import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host=os.environ.get("QP_HOST", "127.0.0.1"), port=int(os.environ.get("QP_PORT", "8787")))
