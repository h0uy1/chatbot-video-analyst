from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain.agents import create_agent

async def create_vision_agent(model, get_path, stack):
    
    client = MultiServerMCPClient(
        {
            "vision": {
                "transport": "stdio",
                "command": "uv",
                "args": ["run", get_path("vision.py")],
            },
        })
    print("Starting persistent vision MCP session...", flush=True)
    session = await stack.enter_async_context(client.session("vision"))
    tools = await load_mcp_tools(session)
    
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt="You are a vision agent. Your task is to analyze images and provide descriptions. Use the provided tools to perform the analysis.",
    )
    
    return agent, {tool.name: tool for tool in tools}
