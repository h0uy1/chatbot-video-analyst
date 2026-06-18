import os
from contextlib import AsyncExitStack
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain.tools import tool
from langchain.agents.middleware import HumanInTheLoopMiddleware 
from langgraph.types import Command
from .generation_agent import create_generation_agent
from .model import build_local_model
from .transcription_agent import create_transcription_agent
from .vision_agent import create_vision_agent


class AgentRuntime:
    def __init__(self, supervisor_agent, mcp_stack):
        self.supervisor_agent = supervisor_agent
        self.mcp_stack = mcp_stack

    async def aclose(self):
        await self.mcp_stack.aclose()


def get_path(file_name):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, "..", "mcp_server", file_name))


def get_messages(result):
    if hasattr(result, "value") and isinstance(result.value, dict):
        return result.value.get("messages", [])

    if isinstance(result, dict):
        return result.get("messages", [])

    return []


def get_last_message_content(result):
    messages = get_messages(result)
    if not messages:
        return ""

    content = getattr(messages[-1], "content", messages[-1])

    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                text_parts.append(str(item["text"]))
            else:
                text_parts.append(str(item))
        content = "\n".join(text_parts)

    return str(content).replace("<|im_end|>", "").strip()


@tool
def ask_user():
    """
    Ask the human user only when a file-based task cannot proceed or required task details.

    """
    
    return "Waiting for user clarification."

async def create_agent_with_tools():
    mcp_stack = AsyncExitStack()
    chat_model = build_local_model()

    try:
        transcription_agent, _transcription_tools = await create_transcription_agent(
            chat_model,
            get_path,
            mcp_stack,
        )
        vision_agent, _vision_tools = await create_vision_agent(
            chat_model,
            get_path,
            mcp_stack,
        )
        generation_tools = await create_generation_agent(
            chat_model,
            get_path,
            mcp_stack,
        )
    except Exception:
        await mcp_stack.aclose()
        raise

    @tool
    async def transcript_audio(file_path: str) -> str:
        """
        Transcribe the audio from the given audio or video file path and return the text.
        """
        result = await transcription_agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": f"Transcribe this file: {file_path}",
                    }
                ]
            },
        )
        return get_last_message_content(result)

    @tool
    async def analyze_video(file_path: str) -> str:
        """
        Analyze visible content in the given video file path and return a description.
        """
        result = await vision_agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": f"Analyze this video visually: {file_path}",
                    }
                ]
            },
        )
        return get_last_message_content(result)

    system_prompt = """
    You are a helpful assistant with video analysis tools.
    
    Your Job:
    You are responsible for answering general user questions and handling requests related to video analysis, transcription, and file generation. You have access to the following tools:
    1. ask_user: Use this tool only when a video, transcription, or file-generation request is missing a required file path or required task detail. Do not use this tool for general questions; answer those directly.
    2. transcript_audio: Use this tool to transcribe audio from video files into text.
    3. analyze_video: Use this tool to analyze the content of video files and provide descriptions or insights.
    4. generate_powerpoint: Use this tool for generate PowerPoint presentations purpose only based on title and structured slide data.
    5. generate_pdf: Use this tool for generate PDF reports purpose only based on title and summary text.

    Tool orchestration rules:
    - Do not assume the server has already routed the request. Decide which tool or tools are needed from the user request and context.
    - If the user asks for a PowerPoint from an uploaded video, call transcript_audio first, convert the transcript into a concise slide outline, then call generate_powerpoint.
    - If the user asks for a PDF summary of the discussion, use the provided conversation history as source material, summarize it, then call generate_pdf.
    - If the user asks for analysis and generation in one request, call the required analysis/transcription tools first, then call the generation tool.
    - Answer general knowledge or conversational questions directly without using tools.
    - If a required video file path or required task detail is missing for a video, transcription, or file-generation task, use ask_user.

    Break down user requests into appropriate tool calls and coordinate the results.
    When a request involves multiple actions, use multiple tools in sequence.
    Always confirm what was done in the final response.
    Please make sure u have output the filepath before telling the user u have done it.
    
    """

    tools = [ask_user, transcript_audio, analyze_video, *generation_tools.values()]
    
    print("\n=== MCP TOOLS LOADED ===")
    for loaded_tool in tools:
        print("Tool:", loaded_tool.name)
        print("Description:", loaded_tool.description)
        print("Args:", getattr(loaded_tool, "args", None))
        
    agent = create_agent(
        model=chat_model,
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=InMemorySaver(),
        middleware=[HumanInTheLoopMiddleware(
            interrupt_on = {
                "ask_user": {
                    "allowed_decisions": ["respond"],
                    "description": "Please provide more details.",
                },
                
            },
            description_prefix="Human clarification required",
            )],
    )
    
    return AgentRuntime(
        supervisor_agent=agent,
        mcp_stack=mcp_stack,
    )

async def ask_agent(agent, message, file_path, thread_id, human_reply=None, history_text=None):
    supervisor_agent = getattr(agent, "supervisor_agent", agent)
    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    if human_reply is not None:
        result = await supervisor_agent.ainvoke(
            Command(
                resume={
                    "decisions": [
                        {
                            "type": "respond",
                            "message": human_reply,
                        }
                    ]
                }
            ),
            config=config,
            version="v2"
        )
        return result

    if file_path:
        full_message = f"""
                    User request:
                    {message}

                    Uploaded video file path:
                    {file_path}

                    Use this file path when calling any video, transcription, vision, or generation tool.

                    Conversation history:
                    {history_text or "No prior conversation history."}
                    """
    else:
        full_message = f"""
                    User request:
                    {message}

                    Conversation history:
                    {history_text or "No prior conversation history."}
                    """

    response =  await supervisor_agent.ainvoke(
         {
            "messages": [
                {
                    "role": "user",
                    "content": full_message,
                }
            ]
        },
        config=config,
        version="v2"
    )
    return response

# if __name__ == "__main__":
    # async def main():
    #     agent = await create_agent_with_tools(model)

    #     response =  await ask_agent(
    #         agent=agent,
    #         message="Transcribe this video file",
    #         file_path=r"C:\Users\User\Downloads\Original_recording5_11.mp4",
    #         thread_id="test_thread_1",
    #     )

    #     print("\n=== AGENT RESPONSE ===")
    #     print(response)

    #     print("\n=== MESSAGES ===")
    #     for msg in response["messages"]:
    #         print(type(msg))
    #         print(msg)
    #         print("tool_calls:", getattr(msg, "tool_calls", None))
    #         print("-" * 50)

    # asyncio.run(main())
