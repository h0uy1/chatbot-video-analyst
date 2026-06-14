import torch
from fastmcp import FastMCP
from transformers import pipeline
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq, pipeline

model_id = "openai/whisper-large-v3"
processor = AutoProcessor.from_pretrained(model_id)
model = AutoModelForSpeechSeq2Seq.from_pretrained(model_id)

mcp = FastMCP("Transcription MCP")

# Initialize the pipeline using the imported model/processor
pipe = pipeline(
    "automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device="cuda" if torch.cuda.is_available() else "cpu"
)

@mcp.tool()
def transcribe(audio_path: str) -> str:
    """Transcribe the audio file at the given path using Whisper."""
    result = pipe(audio_path)
    return result["text"]

if __name__ == "__main__":
    mcp.run()
