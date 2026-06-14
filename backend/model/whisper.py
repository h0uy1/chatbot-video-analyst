import torch
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq, pipeline

model_id = "openai/whisper-large-v3"

processor = AutoProcessor.from_pretrained(model_id)
model = AutoModelForSpeechSeq2Seq.from_pretrained(model_id)