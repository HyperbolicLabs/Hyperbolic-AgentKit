#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import json
import re
from datetime import datetime
import yt_dlp
import importlib.util
import shutil
from pathlib import Path
import video_database as vdb
import concurrent.futures
import argparse

# Constants
CHANNEL_URL = "https://www.youtube.com/@TheRollupCo/videos"
NUM_VIDEOS = 10
DOWNLOAD_DIR = "downloaded_videos"
SPLIT_DIR = "split_videos"  # Local directory for split videos
SEGMENT_LENGTH = 600  # 10 minutes in seconds
COOKIES_FILE = "youtube_cookies.txt"  # Path to cookies file

def clean_filename(filename):
    """
    Clean a string to make it a valid filename by removing special characters
    and replacing spaces with underscores.
    """
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    
    # Remove any non-alphanumeric characters except underscores and hyphens
    filename = re.sub(r'[^\w\-]', '', filename)
    
    # Limit filename length
    if len(filename) > 100:
        filename = filename[:100]
    
    # Add the video ID at the end for uniqueness
    return filename

def setup_directories():
    """Create necessary directories if they don't exist."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(SPLIT_DIR, exist_ok=True)
    os.makedirs("jsonoutputs", exist_ok=True)

def check_cookies_file():
    """Check if the cookies file exists and prompt for creation if needed."""
    if os.path.exists(COOKIES_FILE):
        print(f"Using cookies from: {COOKIES_FILE}")
        return True
    else:
        print(f"No cookies file found at: {COOKIES_FILE}")
        print("YouTube may block downloads without authentication.")
        print("If you encounter 403 Forbidden errors, consider creating a cookies file.")
        print("To create cookies, you can use browser extensions like 'Get cookies.txt'")
        print("from Chrome Web Store or Firefox Add-ons, then save as 'youtube_cookies.txt'")
        print("in the same directory as this script.\n")
        return False

def get_recent_videos():
    """Fetch the most recent videos from the YouTube channel."""
    print(f"Fetching the {NUM_VIDEOS} most recent videos from {CHANNEL_URL}...")
    
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'force_generic_extractor': True,
        'playlist_items': f'1-{NUM_VIDEOS * 2}',  # Fetch more to account for already processed videos
        # Add more options to bypass YouTube restrictions
        'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
        'nocheckcertificate': True,  # Skip HTTPS certificate validation
        'ignoreerrors': True,  # Continue on download errors
        'no_warnings': False,  # Show warnings
        'retries': 10,  # Retry 10 times on failures
        'http_headers': {  # Use a browser-like header
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        },
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(CHANNEL_URL, download=False)
        
        if 'entries' not in result:
            print("Failed to retrieve videos from the channel.")
            return []
        
        videos = []
        for entry in result['entries']:
            if entry:
                video_id = entry['id']
                
                # Skip videos that have already been processed
                if vdb.video_exists(video_id):
                    print(f"Skipping already processed video: {entry.get('title', 'Unknown')} ({video_id})")
                    continue
                
                videos.append({
                    'id': video_id,
                    'title': entry.get('title', 'Unknown Title'),
                    'url': f"https://www.youtube.com/watch?v={video_id}"
                })
                
                # Add to database as pending
                vdb.add_video(video_id, entry.get('title', 'Unknown Title'), 
                              f"https://www.youtube.com/watch?v={video_id}")
                
                # Stop once we have enough new videos
                if len(videos) >= NUM_VIDEOS:
                    break
        
        return videos

def download_video(video):
    """Download a video using yt-dlp."""
    # Clean the title for use in the filename
    clean_title = clean_filename(video['title'])
    
    # Create a filename that includes both the title and ID for uniqueness
    filename = f"{clean_title}_{video['id']}"
    output_template = os.path.join(DOWNLOAD_DIR, f"{filename}.%(ext)s")
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_template,
        'quiet': False,
        # Add more options to bypass YouTube restrictions
        'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
        'nocheckcertificate': True,  # Skip HTTPS certificate validation
        'ignoreerrors': True,  # Continue on download errors
        'no_warnings': False,  # Show warnings
        'retries': 10,  # Retry 10 times on failures
        'fragment_retries': 10,  # Retry 10 times on fragment failures
        'skip_download': False,  # Don't skip download
        'noplaylist': True,  # Download single video, not a playlist
        'http_headers': {  # Use a browser-like header
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Downloading: {video['title']} ({video['id']})")
            ydl.download([video['url']])
        
        # Find the downloaded file
        for file in os.listdir(DOWNLOAD_DIR):
            if file.startswith(clean_title) and video['id'] in file:
                return os.path.join(DOWNLOAD_DIR, file)
        
        print(f"Could not find downloaded file for {video['id']}")
        return None
    except Exception as e:
        print(f"Error downloading {video['id']}: {str(e)}")
        return None

def split_video(video_path, video_id):
    """Split the video into 10-minute segments using ffmpeg."""
    if not os.path.exists(video_path):
        print(f"Video file not found: {video_path}")
        return []
    
    basename = os.path.basename(video_path)
    filename_without_ext = os.path.splitext(basename)[0]
    
    # We'll name segments as "VideoTitle_Part001.mp4", "VideoTitle_Part002.mp4", etc.
    output_pattern = os.path.join(SPLIT_DIR, f"{filename_without_ext}_Part%03d.mp4")
    
    # Get video duration
    cmd = [
        "ffprobe", 
        "-v", "error", 
        "-show_entries", "format=duration", 
        "-of", "json", 
        video_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(json.loads(result.stdout)["format"]["duration"])
        
        # Calculate number of segments
        num_segments = int(duration / SEGMENT_LENGTH) + (1 if duration % SEGMENT_LENGTH > 0 else 0)
        
        # Split video
        print(f"Splitting {basename} into {num_segments} segments...")
        
        cmd = [
            "ffmpeg", 
            "-i", video_path, 
            "-c", "copy", 
            "-map", "0", 
            "-segment_time", str(SEGMENT_LENGTH), 
            "-f", "segment", 
            "-reset_timestamps", "1",
            output_pattern
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        
        # Get list of created segments and add to database
        segments = []
        for file in os.listdir(SPLIT_DIR):
            if file.startswith(filename_without_ext) and file.endswith(".mp4"):
                segment_path = os.path.join(SPLIT_DIR, file)
                segments.append(segment_path)
                
                # Add segment to database
                vdb.add_segment(video_id, segment_path)
        
        return sorted(segments)
    except subprocess.CalledProcessError as e:
        print(f"Error running ffmpeg or ffprobe: {str(e)}")
        print(f"Error output: {e.stderr}")
        return []
    except Exception as e:
        print(f"Error splitting video: {str(e)}")
        return []

# Define this function at module level so it can be pickled for ProcessPoolExecutor
def process_single_segment(segment):
    try:
        print(f"Processing segment: {segment}")
        
        # Import the geminivideo module
        spec = importlib.util.spec_from_file_location("geminivideo", "../podcast_agent/geminivideo.py")
        geminivideo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(geminivideo)
        
        segment_basename = os.path.basename(segment)
        output_path = geminivideo.process_video(segment)
        
        print(f"Successfully processed segment: {segment}")
        print(f"Output saved to: {output_path}")
        
        # Mark as successfully processed in the database
        vdb.mark_segment_processed(segment, output_path)
        
        # Return for cleanup
        return segment
    except Exception as e:
        print(f"Error processing segment {segment}: {str(e)}")
        return None

def process_video_segments_parallel(segments, video_id):
    """Process video segments in parallel using ProcessPoolExecutor."""
    # Process segments in parallel
    max_workers = 3  # Process 3 segments at once
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        successful_segments = list(filter(None, executor.map(process_single_segment, segments)))
    
    # Clean up successfully processed segments
    for segment in successful_segments:
        try:
            if os.path.exists(segment):
                os.remove(segment)
                print(f"Removed processed segment: {segment}")
        except Exception as e:
            print(f"Error removing segment {segment}: {str(e)}")
    
    # Check if all segments for this video are processed
    all_complete = vdb.check_video_complete(video_id)
    
    return len(successful_segments) == len(segments)

def clean_up(video_path):
    """Remove the downloaded video file after processing."""
    try:
        if os.path.exists(video_path):
            os.remove(video_path)
            print(f"Removed downloaded file: {video_path}")
    except Exception as e:
        print(f"Error removing file {video_path}: {str(e)}")

def print_processing_stats():
    """Print statistics about processed videos."""
    stats = vdb.get_processing_stats()
    print("\n--- Processing Statistics ---")
    print(f"Total videos in database: {stats['total_videos']}")
    print(f"Fully processed videos: {stats['processed_videos']}")
    print(f"Pending videos: {stats['pending_videos']}")
    print(f"Total segments: {stats['total_segments']}")
    print(f"Processed segments: {stats['processed_segments']}")
    print(f"Pending segments: {stats['pending_segments']}")
    print("----------------------------\n")

def process_complete_video(video):
    """Process a complete video from download to cleanup."""
    try:
        print(f"Processing video: {video['title']} ({video['id']})")
        
        # Download video
        video_path = download_video(video)
        if not video_path:
            print(f"Skipping {video['id']} due to download failure")
            return False
            
        # Split video into segments
        segments = split_video(video_path, video['id'])
        if not segments:
            print(f"No segments created for {video['id']}")
            return False
            
        # Process segments and clean up after successful processing
        all_processed = process_video_segments_parallel(segments, video['id'])
        
        # Clean up downloaded file
        clean_up(video_path)
        
        if all_processed:
            print(f"Successfully processed all segments for video: {video['title']}")
            return True
        else:
            print(f"Some segments failed to process for video: {video['title']}")
            return False
            
    except Exception as e:
        print(f"Error processing video {video['id']}: {str(e)}")
        return False

def process_pending_videos(parallel=False, max_parallel=2):
    """Process videos that were previously added to the database but not completed."""
    # Check for cookies file before downloading
    has_cookies = check_cookies_file()
    
    pending_videos = vdb.get_unprocessed_videos()
    
    if not pending_videos:
        print("No pending videos to process.")
        return
    
    print(f"Found {len(pending_videos)} pending videos to process.")
    
    if parallel and len(pending_videos) > 1:
        print(f"Processing videos in parallel with {max_parallel} workers...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
            results = list(executor.map(process_complete_video, pending_videos))
        print(f"Parallel processing completed. {sum(results)} videos successfully processed.")
    else:
        # Process videos sequentially (original code)
        for video in pending_videos:
            process_complete_video(video)

def main(parallel_videos=False, max_parallel_videos=2):
    print("Starting YouTube scraper and processor...")
    
    # Initialize database
    vdb.initialize_database()
    
    # Create directories
    setup_directories()
    
    # Check for cookies file
    has_cookies = check_cookies_file()
    
    # Process any pending videos first
    process_pending_videos(parallel=parallel_videos, max_parallel=max_parallel_videos)
    
    # Get recent videos
    videos = get_recent_videos()
    print(f"Found {len(videos)} new videos to process")
    
    if parallel_videos and len(videos) > 1:
        print(f"Processing videos in parallel with {max_parallel_videos} workers...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel_videos) as executor:
            results = list(executor.map(process_complete_video, videos))
        print(f"Parallel processing completed. {sum(results)} videos successfully processed.")
    else:
        # Process videos sequentially (original code)
        for video in videos:
            process_complete_video(video)
    
    # Print final statistics
    print_processing_stats()
    
    print("All videos have been processed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='YouTube scraper and processor for The Rollup podcast.')
    parser.add_argument('--parallel', action='store_true', help='Process videos in parallel')
    parser.add_argument('--max-workers', type=int, default=2, help='Maximum number of parallel video workers (default: 2)')
    args = parser.parse_args()
    
    main(parallel_videos=args.parallel, max_parallel_videos=args.max_workers) 