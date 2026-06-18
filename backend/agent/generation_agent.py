from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain.agents import create_agent

async def create_generation_agent(model, get_path, stack):
    
    client = MultiServerMCPClient(
        {
            "generation": {
                "transport": "stdio",
                "command": "uv",
                "args": ["run", get_path("generation.py")],
            },
        })
    print("Starting persistent generation MCP session...", flush=True)
    session = await stack.enter_async_context(client.session("generation"))
    tools = await load_mcp_tools(session)
    
    
    return {tool.name: tool for tool in tools}
