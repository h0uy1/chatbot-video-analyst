import asyncio
from grpc import aio
import chat_pb2
import chat_pb2_grpc
from agent.main_agent import (
    ask_agent,
    create_agent_with_tools,
    get_last_message_content,
)
from chat_store import ChatStore
from formater import tidy_agent_result


def response_kind_name(response_kind):
    if response_kind == chat_pb2.ASSISTANT_MESSAGE:
        return "assistant_message"
    if response_kind == chat_pb2.CLARIFICATION_REQUEST:
        return "clarification_request"
    if response_kind == chat_pb2.ERROR:
        return "error"
    return "unspecified"


class ChatRouteServicer(chat_pb2_grpc.chatRouteServicer):
    def __init__(self, agent, store):
        self.agent = agent
        self.store = store
        self.latest_video_paths = {}
    @staticmethod
    def extract_interrupt_question(result):
        if isinstance(result, dict):
            interrupts = result.get("__interrupt__")
        else:
            interrupts = getattr(result, "interrupts", None)

        if not interrupts:
            return None

        interrupt = interrupts[0]
        value = interrupt.value
        if isinstance(value, str):
            return value

        action_requests = value.get("action_requests", [])
        if not action_requests:
            return "Can you provide more details?"

        action = action_requests[0]

        args = action.get("args", {})
        question = args.get("question")

        if question:
            return question

        return action.get("description", "Can you provide more details?")
    
    async def userChat(self, request, context):
        """
        Handles a single request from the client and streams back the responses.
        Because this is a server-streaming RPC, this function is an async generator
        that yields responses.
        """
        print(f"Received message from client: {request}")

        try:
            thread_id = request.session_id or "default-session"
            if request.file_path and request.file_path.strip():
                self.latest_video_paths[thread_id] = request.file_path.strip()

            # 2. Resolve file path from current request or previous session memory
            resolved_file_path = (
                self.latest_video_paths.get(thread_id, "")
                or self.store.get_latest_file_path(thread_id)
            )

            self.store.add_message(
                session_id=thread_id,
                role="user",
                content=request.message,
                file_path=resolved_file_path,
            )
            history_text = self.store.get_history_text(thread_id)
            result = await ask_agent(
                agent=self.agent,
                message=request.message,
                file_path=resolved_file_path,
                thread_id=thread_id,
                human_reply= f"{request.message}"if request.is_human_reply else None,
                history_text=history_text,
            )
            clarification_question = self.extract_interrupt_question(result)

            print("\n===== AGENT RESULT =====")
            print(tidy_agent_result(result))
            print("========================\n")
            if clarification_question:
                response = clarification_question
                response_kind = chat_pb2.CLARIFICATION_REQUEST
            elif "response" not in locals():
                response = get_last_message_content(result)
                response_kind = chat_pb2.ASSISTANT_MESSAGE

        except Exception as e:
            import traceback
            traceback.print_exc()
            response = f"Error processing agent request: {str(e)}"
            response_kind = chat_pb2.ERROR

        self.store.add_message(
            session_id=request.session_id or "default-session",
            role="assistant",
            content=response,
            response_kind=response_kind_name(response_kind),
        )

        yield chat_pb2.userResponse(
            message=response,
            kind=response_kind,
            session_id=request.session_id,
        )

    async def getChatHistory(self, request, context):
        messages = self.store.get_messages(request.session_id or "default-session")
        return chat_pb2.chatHistoryResponse(
            messages=[
                chat_pb2.storedChatMessage(
                    id=message["id"],
                    session_id=message["session_id"],
                    role=message["role"],
                    content=message["content"],
                    file_path=message["file_path"],
                    response_kind=message["response_kind"],
                    created_at=message["created_at"],
                )
                for message in messages
            ]
        )

    async def clearChatHistory(self, request, context):
        self.store.clear_history()
        self.latest_video_paths.clear()
        return chat_pb2.clearChatHistoryResponse(
            success=True,
            message="Chat history cleared.",
        )


async def serve():
    agent = await create_agent_with_tools()
    try:
        store = ChatStore()
        server = aio.server()
        chat_pb2_grpc.add_chatRouteServicer_to_server(ChatRouteServicer(agent, store), server)
        server.add_insecure_port('[::]:50051')
        await server.start()
        print("Chat server started on port 50051...")
        await server.wait_for_termination()
    finally:
        await agent.aclose()

if __name__ == '__main__':
    asyncio.run(serve())
