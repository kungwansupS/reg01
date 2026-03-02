import os
import sys

# Ensure imports work when running from repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dev.realtime_verifier.runner import main


def test_realtime_verifier_smoke_import():
    assert callable(main)
