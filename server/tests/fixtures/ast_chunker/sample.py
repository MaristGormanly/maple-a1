"""Fixture for ast_chunker Python tests."""

import math


def add(a, b):
    return a + b


async def fetch_user(user_id):
    return {"id": user_id, "name": "test"}


class Calculator:
    """A simple calculator."""

    def __init__(self, initial=0):
        self.value = initial

    def add(self, other):
        self.value += other
        return self.value

    def multiply(self, other):
        self.value *= other
        return self.value


def _internal_helper():
    return math.pi
