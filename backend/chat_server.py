from concurrent import futures
import grpc
import chat_pb2
import chat_pb2_grpc

class ChatRouteServicer(chat_pb2_grpc.chatRouteServicer):
    def userChat(self, request_iterator, context):
        for chat_message in request_iterator:
            print(f"Received message: {chat_message.message}")
            response = chat_pb2.userResponse(message=f"Echo: {chat_message.message} from server")
            yield response
        
        
def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    chat_pb2_grpc.add_chatRouteServicer_to_server(ChatRouteServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("Server started on port 50051")
    server.wait_for_termination()
    
if __name__ == '__main__':
    serve()
