"""Test configuration.

Force the dataset store onto an in-memory SQLite database and point uploads at a
throwaway temp dir, so tests never touch the persistent ``data/`` directory and
stay isolated from each other's on-disk state. Set here (before any test module
imports ``dataset_insight.api.main``, which reads both at import time).
"""
import os
import tempfile

os.environ.setdefault("DATASET_INSIGHT_DB", ":memory:")
os.environ.setdefault(
    "DATASET_INSIGHT_DATA", os.path.join(tempfile.gettempdir(), "dataset_insight_test")
)
