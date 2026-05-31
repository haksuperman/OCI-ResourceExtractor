#!/usr/bin/env python3
import argparse
import getpass
import os
import secrets
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auth_utils import generate_password_hash  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description="Run the web app with local in-memory form login enabled."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8088, type=int)
    parser.add_argument("--username", default="admin")
    parser.add_argument("--ttl-minutes", default=480, type=int)
    parser.add_argument("--cookie-secure", action="store_true")
    args = parser.parse_args()

    password = getpass.getpass("Login password: ")
    if not password:
        print("Password must not be empty.", file=sys.stderr)
        return 1

    os.environ["OCI_EXTRACTOR_AUTH_ENABLED"] = "true"
    os.environ["OCI_EXTRACTOR_USERNAME"] = args.username
    os.environ["OCI_EXTRACTOR_PASSWORD_HASH"] = generate_password_hash(password)
    os.environ["OCI_EXTRACTOR_SESSION_SECRET"] = secrets.token_urlsafe(48)
    os.environ["OCI_EXTRACTOR_SESSION_TTL_MINUTES"] = str(args.ttl_minutes)
    os.environ["OCI_EXTRACTOR_COOKIE_SECURE"] = "true" if args.cookie_secure else "false"

    print(f"Web app: http://{args.host}:{args.port}")
    print(f"Username: {args.username}")
    print("Password: hidden input used for this process only")

    import uvicorn  # noqa: E402

    uvicorn.run("web_app:app", host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
