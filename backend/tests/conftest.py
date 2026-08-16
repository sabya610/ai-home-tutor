"""Pytest fixtures: force mock AI mode and an isolated temp database."""

import os
import tempfile

# Must be set before app modules read settings.
os.environ["AI_MODE"] = "mock"
_DB = os.path.join(tempfile.gettempdir(), "ai_home_tutor_test.db")
os.environ["DB_PATH"] = _DB

if os.path.exists(_DB):
    os.remove(_DB)
