from mcp.server.fastmcp import FastMCP
mcp = FastMCP("test")
print("has transport_security:", hasattr(mcp.settings, "transport_security"))
