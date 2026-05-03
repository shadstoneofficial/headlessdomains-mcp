import requests
import json
import threading

def run():
    with requests.get("https://mcp.headlessdomains.com/sse", stream=True) as r:
        for line in r.iter_lines():
            if line:
                line = line.decode('utf-8')
                print("SSE:", line)
                if line.startswith("data: /messages/?session_id="):
                    session_url = "https://mcp.headlessdomains.com" + line.split("data: ")[1]
                    print("Sending POST to", session_url)
                    resp = requests.post(session_url, json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "test", "version": "1.0"}
                        }
                    })
                    print("POST resp:", resp.status_code, resp.text)
                    break

t = threading.Thread(target=run)
t.start()
t.join()