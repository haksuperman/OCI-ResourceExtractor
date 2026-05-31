#!/usr/bin/env python3
import getpass
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auth_utils import generate_password_hash  # noqa: E402


def main():
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        return 1
    if not password:
        print("Password must not be empty.", file=sys.stderr)
        return 1

    print(generate_password_hash(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
