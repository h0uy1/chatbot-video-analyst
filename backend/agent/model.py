# from transformers import AutoModelForCausalLM, AutoTokenizer

# from .custom_transformer_wrapper import QwenTransformersToolChatModel


# def build_local_model():
#     model_id = "Qwen/Qwen2.5-3B-Instruct"
#     tokenizer = AutoTokenizer.from_pretrained(model_id)
#     model = AutoModelForCausalLM.from_pretrained(model_id)

#     return QwenTransformersToolChatModel(
#         model=model,
#         tokenizer=tokenizer,
#         model_id=model_id,
#         max_new_tokens=512,
#         temperature=0.0,
#     )
from langchain_ollama import ChatOllama


def build_local_model():
    return ChatOllama(
        model="qwen2.5:3b",
        base_url="http://localhost:11434",
        temperature=0,
        num_predict=128,
    )