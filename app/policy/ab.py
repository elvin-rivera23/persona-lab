# app/policy/ab.py
import hashlib
import json
from pathlib import Path

from .blender import Blender

CONFIG_PATH = Path(__file__).parent / "policies.json"


def load_policies() -> dict[str, dict[str, float]]:
    """
    Loads policy weight dictionaries from JSON.
    """
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def hash_bucket(user_id: str, buckets: int = 2) -> int:
    """
    Stable bucket assignment using SHA256(user_id) % buckets.
    """
    h = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    return int(h, 16) % buckets


def assign_ab(user_id: str) -> tuple[str, Blender]:
    """
    Assign user_id to A/B group and return (group_name, Blender instance)
    using variant_a for group A, variant_b for group B.
    """
    policies = load_policies()
    group = "A" if hash_bucket(user_id, 2) == 0 else "B"
    variant_name = "variant_a" if group == "A" else "variant_b"
    weights = policies.get(variant_name, policies.get("default", {"serious": 1.0}))
    return group, Blender(weights)


def get_policy(name: str) -> Blender:
    """
    Get a named policy (e.g., 'default', 'variant_a', 'variant_b').
    """
    policies = load_policies()
    weights = policies.get(name)
    if not weights:
        # Fallback to default if not found
        weights = policies.get("default", {"serious": 1.0})
    return Blender(weights)
