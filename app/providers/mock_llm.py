from __future__ import annotations

import random
import time
from typing import Any


class ProviderTimeout(TimeoutError):
    pass


def call_model(payload: dict[str, Any], timeout_secs: float) -> dict[str, Any]:
    simulated = random.uniform(0.05, 1.2)  # 50ms–1.2s latency
    if random.random() < 0.10:  # 10% transient
        time.sleep(min(simulated, timeout_secs))
        raise ProviderTimeout("upstream timeout")
    if random.random() < 0.05:  # 5% hard failure
        raise ValueError("non-transient parse error")

    if simulated > timeout_secs:  # honor timeout
        time.sleep(timeout_secs)
        raise ProviderTimeout("timeout exceeded")

    time.sleep(simulated)
    prompt = payload.get("prompt", "")
    return {"text": f"[MOCK COMPLETION] {prompt[:60]}"}
