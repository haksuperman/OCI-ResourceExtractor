import os
import unittest
from unittest import mock

import auth_utils
import web_app


class WebAuthTest(unittest.TestCase):
    def test_password_hash_round_trip(self):
        password_hash = auth_utils.generate_password_hash("correct horse battery staple")

        self.assertTrue(
            auth_utils.verify_password("correct horse battery staple", password_hash)
        )
        self.assertFalse(auth_utils.verify_password("wrong password", password_hash))
        self.assertTrue(auth_utils.is_supported_password_hash(password_hash))

    def test_signed_session_rejects_tampering_and_expiry(self):
        secret = "s" * 48
        cookie = auth_utils.create_signed_session("admin", secret, 60, now=100)

        self.assertEqual(
            auth_utils.validate_signed_session(cookie, secret, now=159),
            "admin",
        )
        self.assertIsNone(auth_utils.validate_signed_session(cookie, secret, now=161))

        replacement = "A" if cookie[-1] != "A" else "B"
        tampered = f"{cookie[:-1]}{replacement}"
        self.assertIsNone(auth_utils.validate_signed_session(tampered, secret, now=159))

    def test_challenge_response_does_not_verify_with_wrong_password_or_nonce(self):
        password_hash = auth_utils.generate_password_hash("correct password")
        response = auth_utils.create_challenge_response(
            "correct password",
            password_hash,
            "admin",
            "challenge-a",
            "nonce-a",
        )

        self.assertTrue(
            auth_utils.verify_challenge_response(
                password_hash,
                "admin",
                "challenge-a",
                "nonce-a",
                response,
            )
        )
        self.assertFalse(
            auth_utils.verify_challenge_response(
                password_hash,
                "admin",
                "challenge-a",
                "nonce-b",
                response,
            )
        )
        self.assertNotEqual(
            response,
            auth_utils.create_challenge_response(
                "wrong password",
                password_hash,
                "admin",
                "challenge-a",
                "nonce-a",
            ),
        )

    def test_login_form_does_not_submit_raw_password_field(self):
        with mock.patch.dict(
            os.environ,
            {
                "OCI_EXTRACTOR_AUTH_ENABLED": "true",
                "OCI_EXTRACTOR_USERNAME": "admin",
                "OCI_EXTRACTOR_PASSWORD_HASH": auth_utils.generate_password_hash("pw"),
                "OCI_EXTRACTOR_SESSION_SECRET": "s" * 48,
            },
            clear=True,
        ):
            response = web_app._render_login(next_path="/")
            body = response.body.decode("utf-8")

        self.assertIn('type="password"', body)
        self.assertNotIn('name="password"', body)
        self.assertIn('name="client_response"', body)
        self.assertIn("crypto.subtle", body)

    def test_auth_config_rejects_example_values(self):
        with mock.patch.dict(
            os.environ,
            {
                "OCI_EXTRACTOR_AUTH_ENABLED": "true",
                "OCI_EXTRACTOR_USERNAME": "admin",
                "OCI_EXTRACTOR_PASSWORD_HASH": web_app.AUTH_EXAMPLE_HASH,
                "OCI_EXTRACTOR_SESSION_SECRET": "replace-with-long-random-secret",
            },
            clear=True,
        ):
            errors = web_app._auth_config_errors()

        self.assertTrue(any("PASSWORD_HASH" in error for error in errors))
        self.assertTrue(any("SESSION_SECRET" in error for error in errors))

    def test_auth_config_accepts_generated_values(self):
        with mock.patch.dict(
            os.environ,
            {
                "OCI_EXTRACTOR_AUTH_ENABLED": "true",
                "OCI_EXTRACTOR_USERNAME": "admin",
                "OCI_EXTRACTOR_PASSWORD_HASH": auth_utils.generate_password_hash("pw"),
                "OCI_EXTRACTOR_SESSION_SECRET": "s" * 48,
            },
            clear=True,
        ):
            self.assertEqual(web_app._auth_config_errors(), [])


if __name__ == "__main__":
    unittest.main()
