import os
import vertexai
import pathlib
import time
import json
import subprocess
import tempfile
from datetime import datetime, timedelta
from google.api_core.exceptions import ResourceExhausted
from vertexai.generative_models import (
    GenerativeModel,
    Part,
    GenerationConfig
)
from concurrent.futures import ThreadPoolExecutor

# Configuration setup
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/amr/Hyperbolic-AgentKit/eaccservicekey.json"
PROJECT_ID = "evolution-acceleration"
LOCATION = "us-central1"

MAX_RETRIES = 3
INITIAL_BACKOFF = 1
MODEL_ID = "gemini-1.5-pro"
SUPPORTED_FORMATS = {'.mp4': 'video/mp4', '.mov': 'video/quicktime'}

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location=LOCATION)
model = GenerativeModel(MODEL_ID)

def get_file_info(file_path):
    """Extract file extension and validate format"""
    ext = pathlib.Path(file_path).suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported file format: {ext}. Supported formats: {list(SUPPORTED_FORMATS.keys())}")
    return ext, SUPPORTED_FORMATS[ext]

def normalize_timestamp(minutes: int, seconds: int) -> str:
    """Convert total minutes and seconds to HH:MM:SS format"""
    total_seconds = minutes * 60 + seconds
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def timestamp_to_seconds(ts: str) -> float:
    """Convert HH:MM:SS timestamp to seconds"""
    try:
        # First try to parse as MM:SS if it's in that format
        if ts.count(':') == 1:
            m, s = map(int, ts.split(':'))
            if m < 60 and s < 60:  # Valid MM:SS format
                return m * 60 + s
        
        # Otherwise parse as HH:MM:SS
        h, m, s = map(int, ts.split(':'))
        if h > 0 and m >= 60:  # Invalid hours/minutes combination
            return -1
        if m >= 60 or s >= 60:  # Invalid minutes or seconds
            return -1
        return h * 3600 + m * 60 + s
    except:
        print(f"[DEBUG] Invalid timestamp format: {ts}")
        return -1

def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def validate_timestamp(ts: str, max_duration: float) -> bool:
    """Validate timestamp format and ensure it's within video duration."""
    try:
        seconds = timestamp_to_seconds(ts)
        if seconds < 0:
            print(f"[DEBUG] Invalid timestamp format: {ts}")
            return False
        if seconds > max_duration:
            print(f"[DEBUG] Timestamp {ts} ({seconds} seconds) exceeds max duration {max_duration}")
            return False
        return True
    except Exception as e:
        print(f"[DEBUG] Error validating timestamp {ts}: {str(e)}")
        return False

def validate_edit_timestamps(edit, duration_seconds: float) -> bool:
    """Validate start and end timestamps of an edit"""
    start = edit.get("start_time", "")
    end = edit.get("end_time", "")
    
    if not all([start, end]):
        print(f"[DEBUG] Missing timestamps in edit")
        return False
        
    start_seconds = timestamp_to_seconds(start)
    end_seconds = timestamp_to_seconds(end)
    
    if start_seconds < 0 or end_seconds < 0:
        print(f"[DEBUG] Invalid timestamp format")
        return False
        
    if start_seconds >= end_seconds:
        print(f"[DEBUG] Start time must be before end time")
        return False
        
    if start_seconds > duration_seconds or end_seconds > duration_seconds:
        print(f"[DEBUG] Timestamps exceed video duration")
        return False
    
    # Convert timestamps to proper HH:MM:SS format
    edit["start_time"] = format_timestamp(start_seconds)
    edit["end_time"] = format_timestamp(end_seconds)
    
    return True

def trim_video(input_path, output_path, start_time, end_time):
    """Trim video using ffmpeg"""
    print(f"\nTrimming video:\nInput: {input_path}\nOutput: {output_path}\nStart: {start_time}\nEnd: {end_time}")
    
    command = [
        'ffmpeg',
        '-i', input_path,
        '-ss', start_time,
        '-to', end_time,
        '-c', 'copy',  
        '-y',  
        output_path
    ]

    try:
        print(f"Running command: {' '.join(command)}")
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        
        if result.stderr:
            print(f"FFmpeg warnings/info: {result.stderr}")
            
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            print(f"Successfully created clip: {output_path}")
            return True
        else:
            print(f"Failed to create clip - output file is empty or missing: {output_path}")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error: {e.stderr}")
        return False
    except Exception as e:
        print(f"Unexpected error during trimming: {str(e)}")
        return False

def concatenate_videos(clip_paths, output_path):
    """Concatenate multiple video clips into one final video"""
    if not clip_paths:
        print("No clips to concatenate")
        return False

    for clip in clip_paths:
        if not os.path.exists(clip):
            print(f"Missing clip: {clip}")
            return False
        if os.path.getsize(clip) == 0:
            print(f"Empty clip file: {clip}")
            return False

    list_file = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp_file:
            list_file = tmp_file.name
            for clip_path in clip_paths:
                # Escape special characters in file paths
                escaped_path = clip_path.replace("'", "'\\''")
                tmp_file.write(f"file '{escaped_path}'\n")
            tmp_file.flush()  # Ensure all data is written

        command = [
            'ffmpeg',
            '-v', 'error',  # Show all errors
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-c', 'copy',
            '-y',
            output_path
        ]

        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True
        )
        
        if result.stderr:
            print(f"FFmpeg warnings/info: {result.stderr}")
        
        # Verify output file was created
        if not os.path.exists(output_path):
            print("Concatenation failed - no output file created")
            return False
        if os.path.getsize(output_path) == 0:
            print("Concatenation failed - empty output file")
            return False
            
        return True

    except subprocess.CalledProcessError as e:
        print(f"FFmpeg Error ({e.returncode}): {e.stderr}")
        print(f"Command executed: {' '.join(e.cmd)}")
        return False
    except Exception as e:
        print(f"Concatenation Error: {str(e)}")
        return False
    finally:
        if list_file and os.path.exists(list_file):
            os.remove(list_file)

def get_video_duration(video_path):
    """Get video duration using ffprobe"""
    print(f"\n[DEBUG] Getting duration for: {video_path}")
    command = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',  # Select video stream
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]
    try:
        print(f"[DEBUG] Running ffprobe command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        
        print(f"[DEBUG] Raw ffprobe output: '{result.stdout.strip()}'")
        print(f"[DEBUG] Parsed duration: {duration} seconds")
        
        if duration <= 0:
            print(f"[DEBUG] Invalid duration received: {duration}")
            return None, None
            
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        
        formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        print(f"[DEBUG] Calculated hours: {hours}")
        print(f"[DEBUG] Calculated minutes: {minutes}")
        print(f"[DEBUG] Calculated seconds: {seconds}")
        print(f"[DEBUG] Formatted duration: {formatted}")
        
        return formatted, duration
    except subprocess.CalledProcessError as e:
        print(f"[DEBUG] FFprobe error: {e.stderr}")
        print(f"[DEBUG] Command output: {e.stdout}")
        return None, None
    except ValueError as e:
        print(f"[DEBUG] Error parsing duration: {str(e)}")
        print(f"[DEBUG] Raw output: {result.stdout if 'result' in locals() else 'No output'}")
        return None, None
    except Exception as e:
        print(f"[DEBUG] Unexpected error getting duration: {str(e)}")
        return None, None

# Main processing function
def process_video(videopath: str, custom_instructions: str = "") -> str:
    """Main function to process video editing workflow"""
    print(f"\nProcessing video: {videopath}")
    
    # Validate input file
    if not os.path.exists(videopath):
        raise FileNotFoundError(f"Video file not found: {videopath}")
    
    # Get file format information
    file_ext, mime_type = get_file_info(videopath)
    base_name = pathlib.Path(videopath).stem
    
    # Create output directory
    output_dir = os.path.join(os.path.dirname(videopath), f"{base_name}_edits")
    os.makedirs(output_dir, exist_ok=True)
    print(f"Created output directory: {output_dir}")
    
    # Get video duration
    formatted_duration, duration_seconds = get_video_duration(videopath)
    if formatted_duration is None:
        raise ValueError("Failed to get video duration")

    print(f"Video duration: {formatted_duration}")

    try:
        print(f"\nReading video file: {videopath}")
        video_bytes = pathlib.Path(videopath).read_bytes()
        print(f"Successfully read {len(video_bytes)} bytes")
        video_file = Part.from_data(video_bytes, mime_type=mime_type)
        print(f"Created Part object with mime_type: {mime_type}")
    except Exception as e:
        print(f"Error reading video file: {str(e)}")
        raise

    # Define response schema
    response_schema = {
        "type": "object",
        "properties": {
            "edits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "start_time": {"type": "string", "pattern": "^[0-9]{2}:[0-9]{2}:[0-9]{2}$"},
                        "end_time": {"type": "string", "pattern": "^[0-9]{2}:[0-9]{2}:[0-9]{2}$"},
                        "keep": {"type": "boolean"},
                        "reason": {"type": "string"}
                    },
                    "required": ["start_time", "end_time", "keep", "reason"]
                }
            }
        },
        "required": ["edits"]
    }

    generation_config = GenerationConfig(
        response_mime_type="application/json",
        response_schema=response_schema,
        temperature=0.1,
        max_output_tokens=8192,
        candidate_count=1
    )

    # Calculate maximum minutes and seconds for clearer prompt
    max_minutes = int(duration_seconds // 60)
    max_seconds = int(duration_seconds % 60)
    print(f"\n[DEBUG] Calculated prompt constraints:")
    print(f"[DEBUG] Video duration in seconds: {duration_seconds}")
    print(f"[DEBUG] Max minutes allowed: {max_minutes}")
    print(f"[DEBUG] Max seconds allowed: {max_seconds}")
    print(f"[DEBUG] Formatted duration: {formatted_duration}")

    prompt = f"""
    Analyze this video and provide detailed editing suggestions in strict JSON format.
    The video is exactly {formatted_duration} long ({duration_seconds} seconds).

    CRITICAL TIMESTAMP RULES:
    1. Use MM:SS format (e.g. "01:30" for 1 minute 30 seconds)
    2. NO timestamp can exceed {max_minutes}:{max_seconds:02d}
    3. Start time must be before end time
    4. Segments must be in chronological order
    5. Each segment must be at least 10 seconds long
    
    Example valid timestamps for this video:
    - "00:00" for start
    - "01:00" for 1 minute
    - "27:45" for 27 minutes 45 seconds
    - "{max_minutes}:{max_seconds:02d}" for end

    Return segments marked with "keep": true for content to retain, "keep": false for content to remove.
    Keep segment descriptions under 50 characters.

    EDITING GUIDELINES:
    Focus on identifying:
    1. Key discussion points to keep
    2. Any technical issues or dead air to remove
    3. Sections that might need trimming for pacing
    {custom_instructions if custom_instructions else ""}
    """

    contents = [video_file, prompt]

    for attempt in range(MAX_RETRIES):
        try:
            print(f"\nAttempt {attempt + 1} of {MAX_RETRIES}")
            print("Sending request to Gemini API...")
            print(f"Prompt length: {len(prompt)} characters")
            print(f"Video size: {len(video_bytes)} bytes")
            
            response = model.generate_content(contents, generation_config=generation_config)
            print("\nReceived response from Gemini API")
            print(response)
            
            if not response.text:
                print("Error: Empty response from API")
                continue
            
            # Clean and validate JSON response
            response_text = response.text.strip()
            if not response_text.startswith("{"):
                print("Error: Response is not in JSON format")
                print(f"Response starts with: {response_text[:100]}")
                continue

            try:
                # Handle potential truncation by ensuring the JSON is complete
                if not response_text.endswith("}"):
                    print("Warning: JSON response appears truncated")
                    last_brace = response_text.rfind("}")
                    if last_brace > 0:
                        response_text = response_text[:last_brace+1]
                        print("Attempted to fix truncated JSON")
                
                response_json = json.loads(response_text)
                print(f"\nParsed JSON response: {json.dumps(response_json, indent=2)}")
                
                # Save edits JSON to output directory
                edits_file = os.path.join(output_dir, f"{base_name}_edits.json")
                with open(edits_file, 'w') as f:
                    json.dump(response_json, f, indent=2)
                print(f"Saved edits to: {edits_file}")
                
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                print(f"Failed text: {response_text[:200]}...")
                continue

            if "edits" not in response_json:
                print("Invalid response format - missing 'edits' key")
                print(f"Available keys: {list(response_json.keys())}")
                continue

            edits = response_json["edits"]
            if not edits:
                print("No edits suggested by Gemini")
                return None

            # Validate all edits first
            valid_edits = []
            last_end_time = 0
            
            for i, edit in enumerate(edits):
                if not edit.get("keep", False):
                    print(f"Skipping edit {i} - marked as not keep")
                    continue
                    
                if not validate_edit_timestamps(edit, duration_seconds):
                    print(f"Skipping edit {i} - invalid timestamps")
                    continue
                    
                start_seconds = timestamp_to_seconds(edit["start_time"])
                if start_seconds < last_end_time:
                    print(f"Skipping edit {i} - overlaps with previous edit")
                    continue
                    
                last_end_time = timestamp_to_seconds(edit["end_time"])
                valid_edits.append(edit)

            if not valid_edits:
                print("No valid edits found after validation")
                return None

            # Process edits with parallel trimming
            trimmed_clips = []
            print("\nProcessing video edits:")
            with ThreadPoolExecutor() as executor:
                futures = []
                clip_paths = []  # Store paths for verification
                
                for i, edit in enumerate(valid_edits):
                    clip_name = os.path.join(output_dir, f"{base_name}_clip_{i}{file_ext}")
                    clip_paths.append(clip_name)
                    print(f"\nSubmitting edit {i}:")
                    print(f"Start: {edit['start_time']}, End: {edit['end_time']}")
                    print(f"Output: {clip_name}")
                    
                    futures.append(executor.submit(
                        trim_video,
                        videopath,
                        clip_name,
                        edit['start_time'],
                        edit['end_time']
                    ))

                # Collect successful results
                print("\nWaiting for clip generation to complete...")
                trimmed_clips = []
                for i, (future, clip_path) in enumerate(zip(futures, clip_paths)):
                    try:
                        if future.result():
                            if os.path.exists(clip_path) and os.path.getsize(clip_path) > 0:
                                trimmed_clips.append(clip_path)
                                print(f"Successfully processed clip {i}: {clip_path}")
                            else:
                                print(f"Clip {i} was not created or is empty: {clip_path}")
                        else:
                            print(f"Failed to process clip {i}")
                    except Exception as e:
                        print(f"Error processing clip {i}: {str(e)}")

            if trimmed_clips:
                print(f"\nSuccessfully generated {len(trimmed_clips)} clips")
                output_path = os.path.join(output_dir, f"{base_name}_edited{file_ext}")
                print(f"Attempting to concatenate clips to: {output_path}")
                if concatenate_videos(trimmed_clips, output_path):
                    # Cleanup temporary clips
                    for clip in trimmed_clips:
                        os.remove(clip)
                    return output_path
                return None

            break  # Exit retry loop on success

        except ResourceExhausted as e:
            if attempt < MAX_RETRIES - 1:
                sleep_time = INITIAL_BACKOFF * (2 ** attempt)
                print(f"Rate limited. Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
            else:
                raise
        except Exception as e:
            print(f"Error during processing: {str(e)}")
            if attempt == MAX_RETRIES - 1:
                raise

    return None

# Execute the workflow
if __name__ == "__main__":
    
    # This will be the array of video files to process
    # Example: input_files = ["/User/Videos/HPC.mp4", "/User/Videos/HPC2.mp4", "/User/Videos/HPC3.mp4"]
    input_files = []
    
    for video_path in input_files:
        try:
            print(f"\nProcessing {video_path}")
            
            # Get custom editing instructions
            print("\nEnter any specific editing instructions (or press Enter to skip):")
            print("Example: 'Remove all pauses longer than 2 seconds' or 'Focus on technical discussions'")
            print("Instructions: ", end='', flush=True)
            
            try:
                custom_instructions = input()
            except (KeyboardInterrupt, EOFError):
                print("\nNo custom instructions provided, proceeding with default settings...")
                custom_instructions = ""
            
            output_path = process_video(video_path, custom_instructions.strip())
            if output_path:
                print(f"Success! Final video saved to: {output_path}")
            else:
                print("Processing completed with no output")
        except Exception as e:
            print(f"Error processing {video_path}: {str(e)}")
            continue