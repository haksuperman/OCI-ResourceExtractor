import base64
import binascii
import hashlib
import hmac
import secrets
import time


HASH_ALGORITHM = "pbkdf2_sha256"
DEFAULT_PBKDF2_ITERATIONS = 260000
SESSION_VERSION = "v1"
CHALLENGE_RESPONSE_VERSION = "v1"


def generate_password_hash(password, *, iterations=DEFAULT_PBKDF2_ITERATIONS):
    if not password:
        raise ValueError("password must not be empty")
    salt = secrets.token_hex(16)
    digest = _pbkdf2_digest(password, salt, iterations)
    return f"{HASH_ALGORITHM}${iterations}${salt}${digest}"


def verify_password(password, stored_hash):
    parsed = _parse_password_hash(stored_hash)
    if not parsed:
        return False
    iterations = parsed["iterations"]
    salt = parsed["salt"]
    expected_digest = parsed["digest"]
    actual_digest = _pbkdf2_digest(password, salt, iterations)
    return hmac.compare_digest(actual_digest, expected_digest)


def is_supported_password_hash(stored_hash):
    return _parse_password_hash(stored_hash) is not None


def password_hash_params(stored_hash):
    parsed = _parse_password_hash(stored_hash)
    if not parsed:
        return None
    return {
        "algorithm": HASH_ALGORITHM,
        "iterations": parsed["iterations"],
        "salt": parsed["salt"],
    }


def create_challenge_response(password, stored_hash, username, challenge_id, nonce):
    params = password_hash_params(stored_hash)
    if not params:
        raise ValueError("stored_hash is not supported")
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        params["salt"].encode("utf-8"),
        params["iterations"],
    )
    return _sign_challenge(derived_key, username, challenge_id, nonce)


def verify_challenge_response(stored_hash, username, challenge_id, nonce, client_response):
    parsed = _parse_password_hash(stored_hash)
    if not parsed or not client_response:
        return False
    expected_response = _sign_challenge(
        parsed["digest_bytes"],
        username,
        challenge_id,
        nonce,
    )
    return hmac.compare_digest(client_response, expected_response)


def _parse_password_hash(stored_hash):
    try:
        algorithm, iterations_text, salt, expected_digest = stored_hash.split("$", 3)
        iterations = int(iterations_text)
    except (AttributeError, ValueError):
        return None

    if algorithm != HASH_ALGORITHM or iterations <= 0 or not salt or not expected_digest:
        return None
    try:
        decoded_digest = base64.b64decode(expected_digest.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError):
        return None
    if not decoded_digest:
        return None
    return {
        "iterations": iterations,
        "salt": salt,
        "digest": expected_digest,
        "digest_bytes": decoded_digest,
    }


def _challenge_message(username, challenge_id, nonce):
    return f"{CHALLENGE_RESPONSE_VERSION}.{username}.{challenge_id}.{nonce}"


def _sign_challenge(key_bytes, username, challenge_id, nonce):
    digest = hmac.new(
        key_bytes,
        _challenge_message(username, challenge_id, nonce).encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64url_encode_bytes(digest)


def create_signed_session(username, secret, ttl_seconds, *, now=None):
    if not username:
        raise ValueError("username must not be empty")
    if not secret:
        raise ValueError("secret must not be empty")
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")

    issued_at = int(now if now is not None else time.time())
    expires_at = issued_at + int(ttl_seconds)
    username_token = _b64url_encode(username)
    payload = f"{SESSION_VERSION}.{username_token}.{expires_at}"
    signature = _sign(payload, secret)
    return f"{payload}.{signature}"


def validate_signed_session(cookie_value, secret, *, now=None):
    if not cookie_value or not secret:
        return None

    try:
        version, username_token, expires_text, signature = cookie_value.split(".", 3)
        expires_at = int(expires_text)
    except ValueError:
        return None

    if version != SESSION_VERSION:
        return None

    payload = f"{version}.{username_token}.{expires_at}"
    expected_signature = _sign(payload, secret)
    if not hmac.compare_digest(signature, expected_signature):
        return None

    current_time = int(now if now is not None else time.time())
    if expires_at < current_time:
        return None

    try:
        return _b64url_decode(username_token)
    except (binascii.Error, UnicodeDecodeError):
        return None


def _pbkdf2_digest(password, salt, iterations):
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return base64.b64encode(derived).decode("ascii")


def _sign(payload, secret):
    digest = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64url_encode_bytes(digest)


def _b64url_encode(value):
    return _b64url_encode_bytes(value.encode("utf-8"))


def _b64url_encode_bytes(value):
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value):
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}").decode("utf-8")
