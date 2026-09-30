"""Servidor HTTP sin dependencias externas para el laboratorio Lab07."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


DB_PATH = Path(os.environ.get("DB_PATH", "/data/lab07.sqlite3"))
INSTANCE_ID = os.environ.get("INSTANCE_ID", "local")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "local-lab07-shared-secret-change-before-deploying").encode()
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@lab07.local").strip().lower()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Lab07Demo!")
SESSION_SECONDS = 8 * 60 * 60
ITEM_PATH = re.compile(r"^/api/items/(\d+)$")
FORM_ITEM_PATH = re.compile(r"^/items/(\d+)/(update|delete)$")


def database() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=15000")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split(":", 1)
        candidate = hash_password(password, bytes.fromhex(salt_hex)).split(":", 1)[1]
        return hmac.compare_digest(candidate, digest_hex)
    except (ValueError, TypeError):
        return False


def initialize_database() -> None:
    with database() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                quantity INTEGER NOT NULL CHECK(quantity >= 0),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO users(email, password_hash) VALUES (?, ?)",
            (ADMIN_EMAIL, hash_password(ADMIN_PASSWORD)),
        )


def issue_token(user_id: int) -> str:
    payload = f"{user_id}:{int(time.time()) + SESSION_SECONDS}".encode()
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    signature = hmac.new(SESSION_SECRET, encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def read_token(token: str) -> int | None:
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(SESSION_SECRET, encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
        user_id, expiration = payload.split(":", 1)
        if int(expiration) < time.time():
            return None
        return int(user_id)
    except (ValueError, UnicodeDecodeError, binascii.Error, OverflowError):
        return None


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate_item(data: dict[str, object]) -> tuple[str, str, int]:
    name = data.get("name")
    description = data.get("description", "")
    quantity = data.get("quantity")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise ValueError("El nombre debe tener entre 1 y 100 caracteres")
    if not isinstance(description, str) or len(description) > 500:
        raise ValueError("La descripción no puede superar 500 caracteres")
    if isinstance(quantity, bool) or not isinstance(quantity, int) or not 0 <= quantity <= 1_000_000:
        raise ValueError("La cantidad debe ser un entero entre 0 y 1000000")
    return name.strip(), description.strip(), quantity


def item_as_dict(row: sqlite3.Row) -> dict[str, object]:
    return dict(row)


CSS = """
*{box-sizing:border-box}body{font-family:system-ui,sans-serif;max-width:1000px;margin:0 auto;padding:28px;color:#182433;background:#f4f7fb}
header{display:flex;justify-content:space-between;align-items:center;gap:1rem}h1{margin:.25rem 0}h2{margin-top:0}
.card{background:white;border:1px solid #dbe4ee;border-radius:12px;padding:22px;margin:18px 0;box-shadow:0 4px 14px #12243a0a}
label{display:block;font-weight:600;margin:10px 0 4px}input{width:100%;padding:10px;border:1px solid #9fb0c2;border-radius:6px;font:inherit}
button{background:#1456a0;color:white;border:0;border-radius:6px;padding:9px 14px;font:inherit;cursor:pointer}.danger{background:#ae2d38}
.muted{color:#58677a}.error{color:#ae2d38}.badge{background:#e0edff;color:#16477c;border-radius:99px;padding:5px 10px;font-size:.9rem}
table{width:100%;border-collapse:collapse}td,th{padding:12px 8px;border-bottom:1px solid #dbe4ee;text-align:left;vertical-align:top}
.row-actions{display:flex;gap:6px;align-items:end;flex-wrap:wrap}.row-actions input{max-width:180px}.row-actions button{white-space:nowrap}
@media(max-width:700px){body{padding:14px}header{display:block}table,tbody,tr,td{display:block}thead{display:none}tr{border-bottom:2px solid #dbe4ee;padding:8px 0}td{border:0;padding:4px}}
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "Lab07/1.0"

    def _send(self, status: int, body: bytes, content_type: str, extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Backend-Id", INSTANCE_ID)
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: object, extra: dict[str, str] | None = None) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8", extra)

    def _html(self, status: int, content: str, title: str = "Lab07") -> None:
        page = f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{CSS}</style></head><body>{content}</body></html>'
        self._send(status, page.encode(), "text/html; charset=utf-8")

    def _redirect(self, location: str, cookie: str | None = None) -> None:
        headers = {"Location": location}
        if cookie is not None:
            headers["Set-Cookie"] = cookie
        self._send(303, b"", "text/plain", headers)

    def _read_body(self) -> dict[str, object]:
        size = int(self.headers.get("Content-Length", "0"))
        if size > 16_384 or size < 0:
            raise ValueError("Solicitud demasiado grande")
        raw = self.rfile.read(size)
        if "application/json" in self.headers.get("Content-Type", ""):
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("Se esperaba un objeto JSON")
            return parsed
        parsed = parse_qs(raw.decode(), keep_blank_values=True)
        return {key: values[-1] for key, values in parsed.items()}

    def _user(self) -> sqlite3.Row | None:
        authorization = self.headers.get("Authorization", "")
        token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
        if not token:
            jar = cookies.SimpleCookie()
            try:
                jar.load(self.headers.get("Cookie", ""))
                token = jar["lab07_session"].value if "lab07_session" in jar else ""
            except cookies.CookieError:
                return None
        user_id = read_token(token)
        if user_id is None:
            return None
        with database() as connection:
            return connection.execute("SELECT id, email FROM users WHERE id=?", (user_id,)).fetchone()

    def _require_user(self) -> sqlite3.Row | None:
        user = self._user()
        if user is None:
            if urlsplit(self.path).path.startswith("/api/"):
                self._json(401, {"error": "Autenticación requerida"})
            else:
                self._redirect("/login")
        return user

    def _same_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        return origin == f"http://{self.headers.get('Host')}" or origin == f"https://{self.headers.get('Host')}"

    def _login_page(self, error: str = "") -> None:
        message = f'<p class="error">{html.escape(error)}</p>' if error else ""
        self._html(200, f'<main class="card" style="max-width:440px;margin:8vh auto"><h1>Secure Inventory</h1><p class="muted">Lab07 · Login y CRUD con balanceo de carga</p>{message}<form method="post" action="/login"><label>Correo</label><input name="email" type="email" required autocomplete="username"><label>Contraseña</label><input name="password" type="password" required autocomplete="current-password"><p><button>Iniciar sesión</button></p></form><p class="muted">Servidor: <span class="badge">{html.escape(INSTANCE_ID)}</span></p></main>', "Iniciar sesión · Lab07")

    def _items_page(self, user: sqlite3.Row) -> None:
        with database() as connection:
            items = connection.execute("SELECT * FROM items ORDER BY id DESC").fetchall()
        rows = "".join(
            f'<tr><td>#{row["id"]}</td><td><strong>{html.escape(row["name"])}</strong><br><span class="muted">{html.escape(row["description"])}</span></td><td>{row["quantity"]}</td><td><form class="row-actions" method="post" action="/items/{row["id"]}/update"><input aria-label="Nuevo nombre" name="name" value="{html.escape(row["name"], quote=True)}" required maxlength="100"><input aria-label="Nueva descripción" name="description" value="{html.escape(row["description"], quote=True)}" maxlength="500"><input aria-label="Nueva cantidad" name="quantity" type="number" min="0" max="1000000" value="{row["quantity"]}" required><button>Guardar</button></form><form method="post" action="/items/{row["id"]}/delete" style="margin-top:6px"><button class="danger" onclick="return confirm(\'¿Eliminar registro?\')">Eliminar</button></form></td></tr>'
            for row in items
        )
        self._html(200, f'<header><div><h1>Secure Inventory</h1><p class="muted">Usuario: {html.escape(user["email"])} · Atendido por <span class="badge">{html.escape(INSTANCE_ID)}</span></p></div><form method="post" action="/logout"><button>Cerrar sesión</button></form></header><section class="card"><h2>Crear registro</h2><form method="post" action="/items"><label>Nombre</label><input name="name" required maxlength="100"><label>Descripción</label><input name="description" maxlength="500"><label>Cantidad</label><input name="quantity" type="number" min="0" max="1000000" value="0" required><p><button>Crear</button></p></form></section><section class="card"><h2>Registros ({len(items)})</h2><table><thead><tr><th>ID</th><th>Artículo</th><th>Cantidad</th><th>Editar o eliminar</th></tr></thead><tbody>{rows}</tbody></table></section><p class="muted">Refresca la página: cambiará el servidor, pero permanecerán la sesión y los datos.</p>', "Inventario · Lab07")

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/health":
            try:
                with database() as connection:
                    connection.execute("SELECT 1 FROM items LIMIT 1").fetchone()
                self._json(200, {"status": "healthy", "backend": INSTANCE_ID})
            except sqlite3.Error:
                self._json(503, {"status": "unhealthy", "backend": INSTANCE_ID})
            return
        if path == "/api/instance":
            self._json(200, {"backend": INSTANCE_ID})
            return
        if path == "/login":
            self._login_page()
            return
        user = self._require_user()
        if user is None:
            return
        if path == "/":
            self._items_page(user)
        elif path == "/api/me":
            self._json(200, {"id": user["id"], "email": user["email"], "backend": INSTANCE_ID})
        elif path == "/api/items":
            with database() as connection:
                rows = connection.execute("SELECT * FROM items ORDER BY id DESC").fetchall()
            self._json(200, {"items": [item_as_dict(row) for row in rows], "backend": INSTANCE_ID})
        else:
            self._json(404, {"error": "Ruta no encontrada"})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if not self._same_origin():
            self._json(403, {"error": "Origen no permitido"})
            return
        if path in ("/login", "/api/login"):
            try:
                data = self._read_body()
                email = str(data.get("email", "")).strip().lower()
                password = str(data.get("password", ""))
                with database() as connection:
                    user = connection.execute("SELECT id, email, password_hash FROM users WHERE email=?", (email,)).fetchone()
                if user is None or not verify_password(password, user["password_hash"]):
                    if path == "/login":
                        self._login_page("Credenciales inválidas")
                    else:
                        self._json(401, {"error": "Credenciales inválidas"})
                    return
                token = issue_token(user["id"])
                cookie = f"lab07_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_SECONDS}"
                if path == "/login":
                    self._redirect("/", cookie)
                else:
                    self._json(200, {"user": user["email"], "backend": INSTANCE_ID, "token": token}, {"Set-Cookie": cookie})
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                self._json(400, {"error": "Solicitud inválida"})
            return
        user = self._require_user()
        if user is None:
            return
        if path in ("/logout", "/api/logout"):
            cookie = "lab07_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"
            if path == "/logout":
                self._redirect("/login", cookie)
            else:
                self._json(200, {"message": "Sesión cerrada"}, {"Set-Cookie": cookie})
            return
        if path not in ("/items", "/api/items") and not FORM_ITEM_PATH.match(path):
            self._json(404, {"error": "Ruta no encontrada"})
            return
        try:
            data = self._read_body()
            if "quantity" in data and isinstance(data["quantity"], str):
                data["quantity"] = int(data["quantity"])
            if path in ("/items", "/api/items"):
                name, description, quantity = validate_item(data)
                timestamp = now_utc()
                with database() as connection:
                    cursor = connection.execute("INSERT INTO items(name,description,quantity,created_at,updated_at) VALUES (?,?,?,?,?)", (name, description, quantity, timestamp, timestamp))
                    item_id = cursor.lastrowid
                if path == "/items":
                    self._redirect("/")
                else:
                    self._json(201, {"id": item_id, "backend": INSTANCE_ID})
                return
            match = FORM_ITEM_PATH.match(path)
            assert match is not None
            item_id = int(match.group(1))
            with database() as connection:
                if match.group(2) == "delete":
                    cursor = connection.execute("DELETE FROM items WHERE id=?", (item_id,))
                else:
                    name, description, quantity = validate_item(data)
                    cursor = connection.execute("UPDATE items SET name=?,description=?,quantity=?,updated_at=? WHERE id=?", (name, description, quantity, now_utc(), item_id))
            self._redirect("/") if cursor.rowcount else self._json(404, {"error": "Registro no encontrado"})
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc) or "Solicitud inválida"})

    def do_PUT(self) -> None:
        self._api_item_mutation("update")

    def do_DELETE(self) -> None:
        self._api_item_mutation("delete")

    def _api_item_mutation(self, action: str) -> None:
        if not self._same_origin():
            self._json(403, {"error": "Origen no permitido"})
            return
        user = self._require_user()
        if user is None:
            return
        match = ITEM_PATH.match(urlsplit(self.path).path)
        if not match:
            self._json(404, {"error": "Ruta no encontrada"})
            return
        item_id = int(match.group(1))
        try:
            with database() as connection:
                if action == "delete":
                    cursor = connection.execute("DELETE FROM items WHERE id=?", (item_id,))
                else:
                    data = self._read_body()
                    name, description, quantity = validate_item(data)
                    cursor = connection.execute("UPDATE items SET name=?,description=?,quantity=?,updated_at=? WHERE id=?", (name, description, quantity, now_utc(), item_id))
            if cursor.rowcount == 0:
                self._json(404, {"error": "Registro no encontrado"})
            else:
                self._json(200, {"id": item_id, "action": action, "backend": INSTANCE_ID})
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc) or "Solicitud inválida"})


def main() -> None:
    initialize_database()
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Lab07 backend {INSTANCE_ID} escuchando en {port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
