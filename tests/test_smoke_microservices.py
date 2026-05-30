#!/usr/bin/env python3
"""Smoke tests for Asyncgram microservices shared library and service imports."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "packages" / "common")]

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{ROOT / 'test_smoke.db'}")


class MicroservicesSmokeTest(unittest.TestCase):
    def test_jwt_roundtrip(self):
        from asyncgram_common.jwt import create_access_token, decode_token_payload

        token = create_access_token(subject=42, role="admin")
        payload = decode_token_payload(token)
        self.assertEqual(payload["sub"], "42")
        self.assertEqual(payload["role"], "admin")

    def test_chat_event_schema(self):
        from asyncgram_common.events import ChatEvent

        event = ChatEvent(type="message.created", broadcast=True, payload={"id": 1})
        self.assertEqual(event.type, "message.created")

    def test_auth_app_import(self):
        from services.auth_service.app.main import app

        self.assertEqual(app.title, "Asyncgram Auth Service")

    def test_chat_app_import(self):
        from services.chat_service.app.main import app

        self.assertEqual(app.title, "Asyncgram Chat Service")

    def test_ws_app_import(self):
        from services.ws_gateway.app.main import app

        self.assertEqual(app.title, "Asyncgram WebSocket Gateway")

    def test_media_app_import(self):
        from services.media_service.app.main import app

        self.assertEqual(app.title, "Asyncgram Media Service")

    def test_admin_app_import(self):
        from services.admin_service.app.main import app

        self.assertEqual(app.title, "Asyncgram Admin Service")


if __name__ == "__main__":
    unittest.main()
