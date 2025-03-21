#!/usr/bin/env python3
"""
YouTube Scraper for The Rollup Podcast
Main entry point for the YouTube scraper application
"""
import os
import sys
import argparse

# Make sure we can import from the current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the youtube_scraper module
from youtube_scraper import main

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='YouTube scraper and processor for The Rollup podcast.')
    parser.add_argument('--parallel', action='store_true', help='Process videos in parallel')
    parser.add_argument('--max-workers', type=int, default=2, help='Maximum number of parallel video workers (default: 2)')
    args = parser.parse_args()
    
    # Run the main function with command line arguments
    main(parallel_videos=args.parallel, max_parallel_videos=args.max_workers) 