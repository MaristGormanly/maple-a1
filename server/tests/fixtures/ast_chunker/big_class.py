"""Fixture: a class large enough to force per-method splitting."""


class BigClass:
    """A class whose total source comfortably exceeds the small token budget
    used in tests, so the chunker is forced to split it into per-method
    chunks plus a class header."""

    def __init__(self, value):
        # Padding to inflate the source size so the class trips the
        # per-test max_tokens budget and the chunker decomposes it.
        self.value = value
        self.history = []
        self.metadata = {}
        self.config = {"a": 1, "b": 2, "c": 3}
        self.flags = set()
        self.cache = {}

    def method_one(self, x):
        # Lots of body text on purpose.
        result = x * self.value
        self.history.append(("one", x, result))
        self.cache[("one", x)] = result
        self.flags.add("one_called")
        return result

    def method_two(self, x, y):
        result = x + y + self.value
        self.history.append(("two", x, y, result))
        self.cache[("two", x, y)] = result
        self.flags.add("two_called")
        return result

    def method_three(self, items):
        total = sum(items) + self.value
        self.history.append(("three", list(items), total))
        self.cache[("three", tuple(items))] = total
        self.flags.add("three_called")
        return total
