from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain.agents import create_agent

async def create_transcription_agent(model, get_path, stack):
    
    client = MultiServerMCPClient(
        {
            "transcription": {
                "transport": "stdio",
                "command": "uv",
                "args": ["run", get_path("transcription.py")],
            }, 
        })
    print("Starting persistent transcription MCP session...", flush=True)
    session = await stack.enter_async_context(client.session("transcription"))
    tools = await load_mcp_tools(session)
    
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt="You are a transcription agent. Your task is to transcribe audio files into text. Use the provided tools to perform the transcription.",
    )
    
    return agent, {tool.name: tool for tool in tools}
