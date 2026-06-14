# import grpc
# import chat_pb2
# import chat_pb2_grpc


# def stream_characters(message):
#     for character in message:
#         yield chat_pb2.userQuery(message=character)


# def main():
#     with grpc.insecure_channel("localhost:50051") as channel:
#         stub = chat_pb2_grpc.chatRouteStub(channel)
#         response_iterator = stub.userChat(stream_characters("Hello, Server!"))

#         for response in response_iterator:
#             print(f"Received message: {response.message}")


# if __name__ == "__main__":
#     main()
