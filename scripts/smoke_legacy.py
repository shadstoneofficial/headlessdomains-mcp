"""Start the legacy service locally and inspect MCP; never execute a tool."""
import asyncio
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import json

from mcp import ClientSession
from mcp.client.sse import sse_client


async def inspect(base):
    async with sse_client(base + "/sse") as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert names == {"search_domain", "lookup_whois", "register_domain", "sync_bio"}, names
            return names


def main():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    env = {**os.environ, "PORT": str(port), "HEADLESSDOMAINS_API_KEY": "",
           "HEADLESSDOMAINS_API_BASE_URL": "http://127.0.0.1:1"}
    process = subprocess.Popen([sys.executable, "server.py"], env=env,
                               cwd=Path(__file__).resolve().parents[1])
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError("Legacy server exited before becoming ready")
            try:
                with urllib.request.urlopen(base + "/healthz", timeout=1) as response:
                    assert json.load(response)["status"] == "ok"
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Legacy server startup timed out")
        with urllib.request.urlopen(base + "/.well-known/mcp/server-card.json", timeout=2) as response:
            card = json.load(response)
        names = asyncio.run(asyncio.wait_for(inspect(base), timeout=15))
        assert names == {tool["name"] for tool in card["tools"]}
        print("PASS: startup, health, discovery, SSE initialize and tools/list; no tool executed")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == "__main__":
    main()
