import os
import subprocess
import sys
import tempfile
from fastmcp import FastMCP
import torch
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq, pipeline

# 1. Initialize FastMCP
mcp = FastMCP("Transcription MCP Server")

MODEL_ID = "openai/whisper-tiny"


device = "cuda:0" if torch.cuda.is_available() else "cpu"
torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

try:
    print("Loading transcription model from local cache...", file=sys.stderr, flush=True)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        MODEL_ID,
        dtype=torch_dtype,
        low_cpu_mem_usage=True,
        use_safetensors=True,
        local_files_only=True,
    )
    processor = AutoProcessor.from_pretrained(MODEL_ID, local_files_only=True)
except Exception:
    print("Transcription model not found in local cache. Downloading from HuggingFace...", file=sys.stderr, flush=True)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        MODEL_ID,
        dtype=torch_dtype,
        low_cpu_mem_usage=True,
        use_safetensors=True,
    )
    processor = AutoProcessor.from_pretrained(MODEL_ID)
model.to(device)

pipe = pipeline(
    "automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    device=device,
    generate_kwargs={
        "task": "transcribe",
        "language": None,
    },
)

def extract_audio_from_video(video_path: str) -> str:
    """Extracts audio from a video file and saves it as a temporary wav file."""
    # Create a temporary file path that ends in .wav
    temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    temp_audio.close() # Close it so ffmpeg can write to it
    
    # Run FFmpeg command to extract audio without re-encoding if possible, or forcing 16kHz wav (Whisper's preference)
    command = [
        "ffmpeg", "-y",                  # Overwrite output file if it exists
        "-i", video_path,               # Input video path
        "-vn",                          # Disable video recording (extract audio only)
        "-acodec", "pcm_s16le",         # Convert to 16-bit PCM (WAV)
        "-ar", "16000",                 # Set audio sample rate to 16kHz (Whisper native)
        "-ac", "1",                     # Convert to mono channel
        temp_audio.name                 # Output path
    ]
    
    # Run the command silently
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return temp_audio.name

@mcp.tool()
def transcribe_audio_file(audio_path: str) -> str:
    """
    Transcribes an audio or video file into written text.
    Use this tool whenever the user provides a video file path, audio file path, 
    audio link, voice recording, or requests a transcription/speech-to-text conversion.
    
    Args:
        audio_path (str): The absolute local system file path to the audio/video file 
                          (e.g., .mp4, .mp3, .wav).
    
    Returns:
        str: The complete raw text transcription of the spoken audio.
    """
    clean_path = os.path.normpath(audio_path.strip("'\""))
    
    if not os.path.exists(clean_path):
        return f"Error: The target file was not found at path: {clean_path}"
        
    temp_wav = None
    try:
        # Check if the file is a video format (like .mp4, .mkv, .mov, etc.)
        _, ext = os.path.splitext(clean_path.lower())
        if ext in ['.mp4', '.mkv', '.mov', '.avi', '.flv', '.webm']:
            print("Transcription: extracting audio track via FFmpeg...", file=sys.stderr, flush=True)
            processing_path = extract_audio_from_video(clean_path)
            temp_wav = processing_path  # Keep track so we can clean it up later
        else:
            processing_path = clean_path

        # Run transcription on the pure audio file
        print("Transcription: running Whisper...", file=sys.stderr, flush=True)
        result = pipe(processing_path)
        print("Transcription: completed.", file=sys.stderr, flush=True)
        return result["text"]
        
    except Exception as e:
        return f"An error occurred during transcription processing: {str(e)}"
        
    finally:
        # Clean up the temporary file if it was created so you don't bloat your storage
        if temp_wav and os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except Exception:
                pass # Fail silently if file is locked

if __name__ == "__main__":
    mcp.run(transport="stdio")
    # testpath = "C:\\Users\\User\\Downloads\\Original_recording5_11.mp4"
    # print("--- Starting Manual Test ---")
    # print(f"Testing path: {testpath}")
    
    # try:
    #     result = transcribe_audio_file(testpath)
    #     print("\n--- Transcription Result ---")
    #     print(result)
    # except Exception as e:
    #     print(f"\n--- Execution Failed ---")
    #     print(e)
