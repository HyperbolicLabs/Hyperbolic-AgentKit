import os
import vertexai
import pathlib
import time
from google.api_core.exceptions import ResourceExhausted
from langchain.output_parsers import StructuredOutputParser
from langchain.output_parsers.structured import ResponseSchema
import json
from functools import wraps
import random

def retry_with_exponential_backoff(
    max_retries=3,
    initial_delay=1,
    exponential_base=2,
    jitter=True
):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            delay = initial_delay

            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except (ResourceExhausted, Exception) as e:
                    retries += 1
                    if retries == max_retries:
                        raise e

                    # Calculate delay with optional jitter
                    if jitter:
                        delay *= exponential_base * (1 + random.uniform(-0.1, 0.1))
                    else:
                        delay *= exponential_base

                    print(f"Attempt {retries} failed. Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/amr/Hyperbolic-AgentKit/eaccservicekey.json"
PROJECT_ID = "evolution-acceleration"
LOCATION = "us-central1"

MAX_RETRIES = 3
INITIAL_BACKOFF = 1

vertexai.init(project=PROJECT_ID, location=LOCATION)

from vertexai.generative_models import (
    GenerativeModel,
    Part,
)

MODEL_ID = "gemini-1.5-pro"
model = GenerativeModel(MODEL_ID)

@retry_with_exponential_backoff(max_retries=3, initial_delay=1)
def process_video(video_path):
    print(f"Processing video: {video_path}")
    video_bytes = pathlib.Path(video_path).read_bytes()
    video_file = Part.from_data(video_bytes, mime_type="video/mov")

    prompt = f"""
    The name of this podcast is The Rollup. There are two hosts in this interview:
    - Andy: Has light blonde, curly hair. His hair is longer on top and styled with a bit of wave. He has a light complexion.
    - Rob: Has short, dark hair with a slightly receding hairline. He has a light to medium skin tone and a short beard that follows his jawline. 

    Any other speakers in this interview are guests, and they should be identified as such.

    Please completely transcribe this interview in its entirety, identify the speakers based on these descriptions, and return the transcript in precisely the following JSON format:
    """

    prompt += """
    [
        {
        "speaker": "Speaker Name",
        "content": "What they said"
        },
        {
        "speaker": "Speaker Name",
        "content": "What they said"
        },
        {
        "speaker": "Speaker Name",
        "content": "What they said"
        }
    ]
    """

    contents = [video_file, prompt]
    responses = model.generate_content(contents)

    cleaned_response = responses.text.strip()
    if cleaned_response.startswith('```json'):
        cleaned_response = cleaned_response[7:]
    if cleaned_response.endswith('```'):
        cleaned_response = cleaned_response[:-3]
    cleaned_response = cleaned_response.strip()
    
    json_data = json.loads(cleaned_response)
    
    response_schemas = [
        ResponseSchema(name="speaker", description="The name of the speaker"),
        ResponseSchema(name="content", description="The content of the speech")
    ]
    
    parser = StructuredOutputParser(response_schemas=response_schemas)
    
    os.makedirs("jsonoutputs", exist_ok=True)
    
    output_filename = os.path.splitext(os.path.basename(video_path))[0] + ".json"
    output_path = os.path.join("jsonoutputs", output_filename)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully wrote transcript to {output_path}")
    return output_path

def main():
    # Define the directory containing the video files
    video_dir = "/Volumes/hyperdrive/splitvids"
    
    # Get all video files in the directory
    supported_extensions = ('.mov', '.mp4', '.avi', '.mkv')  # Add more video extensions if needed
    video_files = [
        os.path.join(video_dir, f) 
        for f in os.listdir(video_dir) 
        if f.lower().endswith(supported_extensions)
    ]
    
    if not video_files:
        print(f"No video files found in {video_dir}")
        return
    
    print(f"Found {len(video_files)} video files to process")
    
    # Process each video file
    for video_path in video_files:
        try:
            process_video(video_path)
        except Exception as e:
            print(f"Failed to process {video_path}: {str(e)}")
            continue
        
        # Add a small delay between processing files to avoid rate limiting
        time.sleep(2)

if __name__ == "__main__":
    main()