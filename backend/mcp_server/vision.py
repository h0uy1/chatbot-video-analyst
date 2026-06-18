from fastmcp import FastMCP
import os
import shutil
import subprocess
import sys
import tempfile
import torch

from transformers import AutoProcessor, AutoModelForImageTextToText


mcp = FastMCP("Vision MCP Server")

MODEL_ID = "HuggingFaceTB/SmolVLM2-500M-Video-Instruct"


try:
    print("Loading vision model from local cache...", file=sys.stderr, flush=True)

    processor = AutoProcessor.from_pretrained(
        MODEL_ID,
        local_files_only=True,
    )

    model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID,
        local_files_only=True,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        device_map="auto",
    )

except Exception:
    print("Vision model not found in local cache. Downloading from HuggingFace...", file=sys.stderr, flush=True)

    processor = AutoProcessor.from_pretrained(MODEL_ID)

    model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        device_map="auto",
    )


def get_video_duration(video_path: str) -> float | None:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
    )

    duration_text = result.stdout.strip()
    return float(duration_text) if duration_text else None


def extract_sample_frames(video_path: str, max_frames: int = 12) -> tuple[str, list[str]]:
    temp_dir = tempfile.mkdtemp(prefix="vision_frames_")

    try:
        duration = get_video_duration(video_path)
    except Exception:
        duration = None

    output_pattern = os.path.join(temp_dir, "frame_%03d.jpg")

    if duration and duration > 0:
        # Uniformly sample frames across the whole video.
        # Example: for 60s video and 12 frames, sample around every 5s.
        interval = duration / max_frames
        select_expr = f"select='not(mod(t,{interval}))',scale=512:-1"
        command = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-vf",
            select_expr,
            "-vsync",
            "vfr",
            "-frames:v",
            str(max_frames),
            output_pattern,
        ]
    else:
        command = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-vf",
            "fps=1,scale=512:-1",
            "-frames:v",
            str(max_frames),
            output_pattern,
        ]

    subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )

    frame_paths = [
        os.path.join(temp_dir, file_name)
        for file_name in sorted(os.listdir(temp_dir))
        if file_name.lower().endswith(".jpg")
    ]

    return temp_dir, frame_paths


@mcp.tool()
def analyze_video_file(video_path: str, message: str) -> str:
    """
    Analyzes a video file and answers visual questions about what appears in it.
    Use this tool whenever the user asks about visible objects, scenes, charts, graphs,
    screenshots, actions, or other visual content in a video.
    """

    clean_path = os.path.normpath(video_path.strip("'\""))

    if not os.path.exists(clean_path):
        return f"Error: The target file was not found at path: {clean_path}"

    temp_dir = None

    try:
        temp_dir, frame_paths = extract_sample_frames(
            clean_path,
            max_frames=12,
        )

        if not frame_paths:
            return "Error: No video frames could be extracted from the file."

        content = []

        for i, frame_path in enumerate(frame_paths, start=1):
            content.append({
                "type": "text",
                "text": f"Frame {i}:"
            })
            content.append({
                "type": "image",
                "path": frame_path
            })

        content.append({
            "type": "text",
            "text": (
                f"User question: {message or 'Describe what is shown in this video.'}\n\n"
                "Instructions:\n"
                "1. Analyze the sampled frames only.\n"
                "2. For each frame, mention only objects that are clearly visible.\n"
                "3. Do not guess or invent objects.\n"
                "4. If you are uncertain, say 'uncertain'.\n"
                "5. After frame-by-frame analysis, answer the user question.\n"
            ),
        })

        messages = [
            {
                "role": "user",
                "content": content,
            }
        ]

        inputs = processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        )

        inputs = inputs.to(model.device)

        outputs = model.generate(
            **inputs,
            max_new_tokens=250,
            do_sample=False,
            repetition_penalty=1.2,
            no_repeat_ngram_size=4,
        )

        generated_tokens = outputs[0][inputs["input_ids"].shape[-1]:]

        result = processor.decode(
            generated_tokens,
            skip_special_tokens=True,
        ).strip()

        return result

    except Exception as e:
        return f"An error occurred during video analysis: {str(e)}"

    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    mcp.run(transport="stdio")
    # testpath = "C:\\Users\\User\\Downloads\\Original_recording5_11.mp4"
    # result = analyze_video_file(testpath,"Analyze this video visually")
    # print("\n--- Vision Result ---")
    # print(result)