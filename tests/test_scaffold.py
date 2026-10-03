"""Smoke test: package imports and state file is valid JSON."""
import json
import os


def test_src_package_importable():
    import src  # noqa: F401


def test_processed_state_is_valid():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "state", "processed.json")) as f:
        data = json.load(f)
    assert "ids" in data and isinstance(data["ids"], list)
