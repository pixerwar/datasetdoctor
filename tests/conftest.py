"""Test configuration.

Force the dataset store onto an in-memory SQLite database so tests never touch
the persistent ``data/datasets.db`` and stay isolated from each other's on-disk
state. Set here (before any test module imports ``dataset_insight.api.main``,
which constructs the store at import time).
"""
import os

os.environ.setdefault("DATASET_INSIGHT_DB", ":memory:")
