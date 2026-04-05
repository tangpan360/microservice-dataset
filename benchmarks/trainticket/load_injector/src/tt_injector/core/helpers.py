from __future__ import annotations

import string
from random import Random


def random_bool(rng: Random) -> bool:
    return rng.choice([True, False])


def random_pick(rng: Random, items: list):
    return rng.choice(items)


def random_text(rng: Random, min_len: int = 4, max_len: int = 10) -> str:
    size = rng.randint(min_len, max_len)
    return "".join(rng.choices(string.ascii_letters, k=size))


def random_phone(rng: Random, min_len: int = 8, max_len: int = 15) -> str:
    size = rng.randint(min_len, max_len)
    return "".join(rng.choices(string.digits, k=size))
