# YouTube Scraper Package

A package for downloading and processing YouTube videos, specifically designed for The Rollup podcast channel. It includes tools for:

- Downloading recent videos
- Splitting videos into manageable segments
- Processing videos with Gemini Video AI
- Tracking processed videos in a SQLite database
- Creating descriptive filenames for videos and segments

## Directory Structure

```
youtube_scraper/
├── README.md                   # This file
├── README_youtube_scraper.md   # Detailed documentation
├── __init__.py                 # Package initialization
├── create_cookies.sh           # Script to help create cookies file
├── db_utilities.py             # Database utility script
├── downloaded_videos/          # Directory for downloaded videos
├── jsonoutputs/                # Directory for JSON outputs
├── main.py                     # Main entry point
├── processed_videos.db         # SQLite database
├── run_youtube_scraper.sh      # Shell script to run the scraper
├── split_videos/               # Directory for split video segments
├── video_database.py           # Database management module
└── youtube_scraper.py          # Core scraper implementation
```

## Features

### Descriptive File Naming

Videos and segments are saved with descriptive names instead of just IDs:

- Video files: `Video_Title_VideoID.mp4`
- Segment files: `Video_Title_VideoID_Part001.mp4`, `Video_Title_VideoID_Part002.mp4`, etc.

This makes it easier to identify videos and segments in your file system.

## Usage

### Basic Usage

To run the YouTube scraper:

```bash
cd youtube_scraper
poetry run python main.py
```

Or use the shell script:

```bash
cd youtube_scraper
./run_youtube_scraper.sh
```

### Parallel Processing

For faster processing, you can enable parallel video processing:

```bash
# Process multiple videos in parallel (default: 2 workers)
poetry run python main.py --parallel

# Specify the maximum number of parallel video workers
poetry run python main.py --parallel --max-workers 3
```

Note: Each video will also process up to 3 segments in parallel, so using more video workers
will increase the overall system load. Adjust the number based on your system's capabilities.

### Database Utilities

To manage the database:

```bash
cd youtube_scraper
poetry run python db_utilities.py --help
```

Common commands:
- `poetry run python db_utilities.py stats` - Show database statistics
- `poetry run python db_utilities.py list` - List videos in database
- `poetry run python db_utilities.py reset` - Reset the database

### Cookie Setup (if needed)

If you encounter 403 Forbidden errors, you may need to set up cookies:

```bash
cd youtube_scraper
./create_cookies.sh
```

Follow the instructions to create a `youtube_cookies.txt` file.

## See Also

For more detailed documentation, see [README_youtube_scraper.md](README_youtube_scraper.md).