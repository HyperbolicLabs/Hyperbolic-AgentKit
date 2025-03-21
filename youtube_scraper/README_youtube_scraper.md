# YouTube Scraper and Processor for The Rollup Podcast

This script automates the process of:
1. Scraping the [The Rollup YouTube channel](https://www.youtube.com/@TheRollupCo/videos)
2. Downloading the most recent 10 videos
3. Splitting the videos into 10-minute segments
4. Processing each segment with Gemini Video AI for transcription
5. Saving the transcriptions as JSON files
6. Tracking processed videos in a SQLite database to avoid duplicates

## Requirements

- Python 3.11+
- ffmpeg and ffprobe (for video splitting and metadata extraction)
- A valid Google Cloud Platform account with access to Vertex AI and Gemini API
- Poetry for dependency management
- SQLite (included with Python)

## Installation

1. Install ffmpeg if not already installed:
   ```
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt-get install ffmpeg
   
   # Windows
   # Download from https://ffmpeg.org/download.html
   ```

2. Install the required Python packages using Poetry:
   ```
   poetry install
   ```

3. Ensure you have a valid Google Cloud Platform service account key file configured in `podcast_agent/geminivideo.py`.

## Usage

Simply run the script using Poetry:

```
poetry run python youtube_scraper.py
```

The script will:
1. Create necessary directories if they don't exist
2. Initialize or connect to the SQLite database
3. Process any pending videos from previous runs
4. Fetch up to 10 new videos from The Rollup YouTube channel (skipping already processed ones)
5. Download each video to the `downloaded_videos` directory
6. Split each video into 10-minute segments stored in the `split_videos` directory
7. Process each segment with Gemini Video AI for transcription
8. Save transcription results as JSON files in the `jsonoutputs` directory
9. Clean up downloaded videos and processed segments after processing
10. Display processing statistics from the database

### Parallel Processing

For faster processing, you can enable parallel processing:

```
# Process segments of each video in parallel (default behavior)
poetry run python youtube_scraper.py

# Process multiple videos in parallel (default: 2 concurrent videos)
poetry run python youtube_scraper.py --parallel

# Process multiple videos in parallel with custom worker count
poetry run python youtube_scraper.py --parallel --max-workers 3
```

By default, the script:
- Processes videos one at a time (sequential)
- Processes up to 3 segments in parallel for each video

When parallel video processing is enabled:
- Multiple videos are processed simultaneously
- Each video still processes up to 3 segments in parallel
- Total concurrent processes = (number of video workers) × (number of segment workers)

**Note:** Be mindful of system resources and API rate limits when using parallel processing.

## Database Management

The script includes a utility tool (`db_utilities.py`) for managing the SQLite database. You can use it to check processing status, view statistics, and manage records.

### Database Utility Commands

```
# View help and available commands
poetry run python db_utilities.py --help

# List all videos in the database (most recent first)
poetry run python db_utilities.py list

# List only processed videos
poetry run python db_utilities.py list --processed

# List only pending/unprocessed videos
poetry run python db_utilities.py list --pending

# Show segments for a specific video
poetry run python db_utilities.py segments VIDEO_ID

# Show database statistics
poetry run python db_utilities.py stats

# Mark a video as processed
poetry run python db_utilities.py mark VIDEO_ID processed

# Mark a video as unprocessed
poetry run python db_utilities.py mark VIDEO_ID unprocessed

# Reset the database (WARNING: deletes all data)
poetry run python db_utilities.py reset
```

## Database Tracking

The script uses an SQLite database (`processed_videos.db`) to track:

- Which videos have been downloaded and processed
- Individual video segments and their processing status
- Timestamps for downloads and processing
- Output paths for the JSON transcriptions

This allows the script to:
- Avoid re-downloading and re-processing videos that have already been completed
- Resume processing of videos that were interrupted in a previous run
- Track processing statistics across multiple runs

## Storage and Cleanup

- **Downloaded Videos**: Videos are temporarily stored in the `downloaded_videos` directory and are automatically deleted after all segments have been processed.
- **Split Segments**: Video segments are stored in the `split_videos` directory and are deleted after successful transcription.
- **JSON Transcripts**: Transcription results are saved in the `jsonoutputs` directory and are not deleted.
- **Database**: Processing history is permanently stored in `processed_videos.db` in the root directory.

## Customization

You can modify the following constants in the script to customize behavior:

- `CHANNEL_URL`: YouTube channel URL to scrape
- `NUM_VIDEOS`: Number of recent videos to process in each run
- `DOWNLOAD_DIR`: Directory to store downloaded videos
- `SPLIT_DIR`: Directory to store split video segments
- `SEGMENT_LENGTH`: Length of each video segment in seconds (default is 600 seconds = 10 minutes)
- `DB_FILE`: Database file path in `video_database.py` (default is "processed_videos.db")

## File Naming Convention

The YouTube scraper uses descriptive filenames for both videos and segments:

### Downloaded Videos

Videos are saved with filenames that combine the title and video ID:
```
Video_Title_VideoID.mp4
```

For example:
```
Illia_Polosukhin_on_The_Upcoming_Explosion_of_User-Owned_AI_Uw5GPwR_mTg.mp4
```

### Video Segments

Segments are named with the video title, ID, and part number:
```
Video_Title_VideoID_Part001.mp4
Video_Title_VideoID_Part002.mp4
```

For example:
```
Illia_Polosukhin_on_The_Upcoming_Explosion_of_User-Owned_AI_Uw5GPwR_mTg_Part001.mp4
```

### JSON Outputs

Corresponding JSON transcription files also use descriptive names matching the video segments.

This naming convention makes it easy to identify and associate videos, segments, and their transcriptions.

## Troubleshooting

- **Error accessing the YouTube channel**: Make sure your network connection allows access to YouTube.
- **ffmpeg errors**: Ensure ffmpeg is properly installed and accessible in your PATH.
- **Gemini Video API errors**: Check your Google Cloud Platform credentials and API quotas.
- **Disk space errors**: Ensure you have sufficient disk space for downloading and splitting videos.
- **Database errors**: If the database becomes corrupted, you can delete `processed_videos.db` to start fresh, but this will lose tracking of already processed videos.

## Notes

- The script will automatically handle retries for Gemini Video API calls using exponential backoff.
- Each video segment is processed sequentially to avoid overloading the API.
- Both original downloaded videos and processed segments are removed after processing to save disk space.
- Run the script regularly with a cron job to keep your transcription database up to date.
- The database can be queried directly using SQLite tools if you need to extract specific information about processed videos. 