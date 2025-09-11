# app/policy/blender.py

import random


class Blender:
    """
    Blending policy for combining multiple personalities/strategies.
    Supports weighted and stochastic blending.
    """

    def __init__(self, policies: dict[str, float]):
        """
        policies: dict of {policy_name: weight}
        Example: {"serious": 0.7, "playful": 0.3}
        """
        self.policies = policies
        self.normalize()

    def normalize(self):
        """Ensure weights sum to 1.0"""
        total = sum(self.policies.values())
        if total > 0:
            for k in self.policies:
                self.policies[k] /= total

    def choose_policy(self, stochastic: bool = True) -> str:
        """
        Choose a policy based on weights.
        - stochastic=True → random weighted choice
        - stochastic=False → return highest-weighted policy
        """
        if stochastic:
            return random.choices(
                population=list(self.policies.keys()), weights=list(self.policies.values()), k=1
            )[0]
        else:
            return max(self.policies, key=self.policies.get)
