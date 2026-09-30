"""Pruebas de integración con dos procesos sobre una base compartida."""

from __future__ import annotations

import http.cookiejar
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AppIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.processes: list[subprocess.Popen[bytes]] = []
        self.ports: list[int] = []
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        for instance in ("test-a", "test-b"):
            import socket

            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            env = os.environ.copy()
            env.update(
                DB_PATH=str(Path(self.temp.name) / "shared.sqlite3"),
                INSTANCE_ID=instance,
                PORT=str(port),
                SESSION_SECRET="test-secret-shared-across-all-instances",
                ADMIN_EMAIL="admin@test.local",
                ADMIN_PASSWORD="TestPassword123!",
            )
            process = subprocess.Popen(
                [sys.executable, "-m", "app.server"],
                cwd=ROOT,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self.processes.append(process)
            self.ports.append(port)
            for _ in range(100):
                try:
                    self.request(port, "GET", "/health")
                    break
                except urllib.error.URLError:
                    if process.poll() is not None:
                        self.fail(process.stderr.read().decode())
                    time.sleep(0.05)
            else:
                self.fail(f"El backend {instance} no inició")

    def tearDown(self) -> None:
        for process in self.processes:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            if process.stderr:
                process.stderr.close()
        self.temp.cleanup()

    def request(self, port: int, method: str, path: str, data: dict | None = None):
        body = json.dumps(data).encode() if data is not None else None
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json"} if body else {},
        )
        try:
            with self.opener.open(request, timeout=3) as response:
                return response.status, json.load(response), response.headers
        except urllib.error.HTTPError as error:
            return error.code, json.load(error), error.headers

    def test_login_crud_shared_between_backends(self) -> None:
        a, b = self.ports
        status, _, _ = self.request(a, "GET", "/api/items")
        self.assertEqual(status, 401)

        status, login, headers = self.request(a, "POST", "/api/login", {"email": "admin@test.local", "password": "TestPassword123!"})
        self.assertEqual(status, 200)
        self.assertEqual(login["backend"], "test-a")
        self.assertIn("HttpOnly", headers["Set-Cookie"])

        status, me, _ = self.request(b, "GET", "/api/me")
        self.assertEqual(status, 200)
        self.assertEqual(me["backend"], "test-b")

        status, created, _ = self.request(a, "POST", "/api/items", {"name": "Router", "description": "Equipo de laboratorio", "quantity": 3})
        self.assertEqual(status, 201)
        item_id = created["id"]

        status, listing, _ = self.request(b, "GET", "/api/items")
        self.assertEqual(status, 200)
        self.assertEqual(listing["items"][0]["name"], "Router")

        status, _, _ = self.request(b, "PUT", f"/api/items/{item_id}", {"name": "Switch", "description": "Actualizado", "quantity": 5})
        self.assertEqual(status, 200)
        status, listing, _ = self.request(a, "GET", "/api/items")
        self.assertEqual(listing["items"][0]["name"], "Switch")

        status, _, _ = self.request(a, "DELETE", f"/api/items/{item_id}")
        self.assertEqual(status, 200)
        status, listing, _ = self.request(b, "GET", "/api/items")
        self.assertEqual(listing["items"], [])

    def test_invalid_login_and_validation(self) -> None:
        a, _ = self.ports
        status, _, _ = self.request(a, "POST", "/api/login", {"email": "admin@test.local", "password": "wrong"})
        self.assertEqual(status, 401)
        self.request(a, "POST", "/api/login", {"email": "admin@test.local", "password": "TestPassword123!"})
        status, body, _ = self.request(a, "POST", "/api/items", {"name": "", "quantity": -1})
        self.assertEqual(status, 400)
        self.assertIn("nombre", body["error"])


if __name__ == "__main__":
    unittest.main()
