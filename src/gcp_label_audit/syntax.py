"""Google Cloud label syntax rules.

From the Resource Manager labels documentation:
- a resource can have up to 64 labels;
- keys are 1-63 characters, values 0-63 characters;
- keys and values contain only lowercase letters, numeric characters,
  underscores and dashes; international characters are allowed (UTF-8);
- keys must start with a lowercase letter or an international character.

Lengths are counted in Unicode characters here.
"""

from __future__ import annotations

MAX_LABELS = 64
MAX_LEN = 63


def _allowed_char(c: str) -> bool:
    if c.isascii():
        return c.islower() or c.isdigit() or c in "_-"
    # International characters: letters/digits that are not uppercase.
    return c.isalnum() and not c.isupper()


def _valid_start(c: str) -> bool:
    if c.isascii():
        return "a" <= c <= "z"
    return c.isalpha() and not c.isupper()


def key_problem(key: str) -> str | None:
    if not key:
        return "key is empty"
    if len(key) > MAX_LEN:
        return f"key is {len(key)} characters (max {MAX_LEN})"
    if not _valid_start(key[0]):
        return "key must start with a lowercase letter or international character"
    bad = sorted({c for c in key if not _allowed_char(c)})
    if bad:
        return f"key has characters not allowed in labels: {''.join(bad)!r}"
    return None


def value_problem(value: str) -> str | None:
    if len(value) > MAX_LEN:
        return f"value is {len(value)} characters (max {MAX_LEN})"
    bad = sorted({c for c in value if not _allowed_char(c)})
    if bad:
        return f"value has characters not allowed in labels: {''.join(bad)!r}"
    return None
