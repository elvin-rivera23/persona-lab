# app/policy/test_blender.py
from blender import Blender


def run_demo():
    # Example: 70% serious, 30% playful
    weights = {"serious": 0.7, "playful": 0.3}
    blender = Blender(weights)

    print("Normalized policies:", blender.policies)

    # Deterministic (always picks max weight)
    print("Deterministic pick:", blender.choose_policy(stochastic=False))

    # Stochastic (random weighted picks)
    picks = [blender.choose_policy(stochastic=True) for _ in range(20)]
    print("Stochastic sample:", picks)


if __name__ == "__main__":
    run_demo()
