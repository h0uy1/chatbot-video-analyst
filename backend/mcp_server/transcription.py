import torch
from fastmcp import FastMCP
from transformers import pipeline
# Import the model and processor from model/whisper.py
from model.whisper import model, processor

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
