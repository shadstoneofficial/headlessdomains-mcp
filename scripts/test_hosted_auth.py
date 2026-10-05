"""Synthetic localhost tests. Upstream HTTP is mocked; no business API calls."""
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client
import server
from hosted_auth import connection_key


class CredentialTests(unittest.TestCase):
    def test_local_only_environment_fallback(self):
        with patch.dict(os.environ, {"HEADLESSDOMAINS_API_KEY": "synthetic-local"}, clear=True):
            self.assertEqual(server._api_key(), "synthetic-local")
            with patch.dict(os.environ, {"PORT": "8080"}):
                self.assertEqual(server._api_key(), "")
            token = connection_key.set("")
            try:
                with patch.object(server.requests, "request") as upstream:
                    self.assertIn("API key required", server.register_domain("fixture.agent")["error"])
                    upstream.assert_not_called()
            finally:
                connection_key.reset(token)

    def test_upstream_errors_do_not_echo_secrets(self):
        token = connection_key.set("synthetic-user-key")
        try:
            with patch.object(server.requests, "request", side_effect=server.requests.RequestException("synthetic-user-key")):
                self.assertNotIn("synthetic-user-key", server.register_domain("fixture.agent")["error"])
        finally:
            connection_key.reset(token)


async def protocol_checks(base):
    async def client(key):
        headers = {"X-API-Key": key} if key else {}
        async with sse_client(base + "/sse", headers=headers) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                assert len((await session.list_tools()).tools) == 4
                # Mock fixture only: requests.request is replaced before server starts.
                response = await session.call_tool("register_domain", {"domain": "fixture.agent"})
                body = json.loads(response.content[0].text)
                if key:
                    assert body["fixture_key"] == key, body
                else:
                    assert "API key required" in body["error"], body
    await asyncio.gather(client("synthetic-A"), client("synthetic-B"), client(None))
    async with httpx.AsyncClient(base_url=base) as client_http:
        response = await client_http.get("/sse?HEADLESSDOMAINS_API_KEY=synthetic-query")
        assert response.status_code == 400
        assert "synthetic-query" not in response.text
        async with client_http.stream("GET", "/sse", headers={"X-API-Key": "synthetic-A"}) as stream:
            lines = stream.aiter_lines()
            async for line in lines:
                if line.startswith("data: "):
                    endpoint = line[6:]
                    break
            for headers in ({}, {"X-API-Key": "synthetic-B"}):
                denied = await client_http.post(endpoint, headers=headers, json={"jsonrpc": "2.0", "method": "ping", "id": 1})
                assert denied.status_code == 404, denied.status_code
            accepted = await client_http.post(endpoint, headers={"X-API-Key": "synthetic-A"}, json={"jsonrpc": "2.0", "method": "initialize", "id": 1, "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "fixture", "version": "1"}}})
            assert accepted.status_code == 202, accepted.status_code


def run_protocol_checks():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    fixture = '''
import server
class FakeResponse:
    def __init__(self, key): self.key = key
    def raise_for_status(self): pass
    def json(self): return {"fixture_key": self.key}
server.requests.request = lambda **kwargs: FakeResponse(kwargs["headers"].get("X-API-Key"))
server.main()
'''
    env = {**os.environ, "PORT": str(port), "HEADLESSDOMAINS_API_KEY": "synthetic-shared-must-not-be-used", "HEADLESSDOMAINS_API_BASE_URL": "http://127.0.0.1:1"}
    p = subprocess.Popen([sys.executable, "-c", fixture], env=env, cwd=Path(__file__).resolve().parents[1])
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            if p.poll() is not None: raise RuntimeError("fixture startup failed")
            try:
                if httpx.get(base + "/healthz", timeout=1).status_code == 200: break
            except httpx.HTTPError: pass
            time.sleep(.1)
        else: raise RuntimeError("fixture startup timeout")
        asyncio.run(asyncio.wait_for(protocol_checks(base), timeout=30))
        print("PASS: concurrent A/B/anonymous, missing key, query rejection, cross-session rejection; mocked upstream only")
    finally:
        p.terminate()
        try: p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CredentialTests)
    if not unittest.TextTestRunner().run(suite).wasSuccessful(): sys.exit(1)
    run_protocol_checks()
