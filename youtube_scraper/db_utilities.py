#!/usr/bin/env python3
import os
import sys
import argparse
import sqlite3
from datetime import datetime
import video_database as vdb

def list_videos(args):
    """List videos in the database with their processing status."""
    conn = sqlite3.connect(vdb.DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if args.processed:
        cursor.execute("""
            SELECT id, title, downloaded_date, processing_complete_date, fully_processed
            FROM videos
            WHERE fully_processed = 1
            ORDER BY processing_complete_date DESC
            LIMIT ?
        """, (args.limit,))
    elif args.pending:
        cursor.execute("""
            SELECT id, title, downloaded_date, fully_processed
            FROM videos
            WHERE fully_processed = 0
            ORDER BY downloaded_date ASC
            LIMIT ?
        """, (args.limit,))
    else:
        cursor.execute("""
            SELECT id, title, downloaded_date, processing_complete_date, fully_processed
            FROM videos
            ORDER BY downloaded_date DESC
            LIMIT ?
        """, (args.limit,))
    
    videos = cursor.fetchall()
    conn.close()
    
    if not videos:
        print("No videos found matching the criteria.")
        return
    
    print(f"Found {len(videos)} videos:")
    print("-" * 100)
    
    for video in videos:
        status = "✅ Processed" if video['fully_processed'] else "⏱️ Pending"
        downloaded = datetime.fromisoformat(video['downloaded_date']).strftime("%Y-%m-%d %H:%M:%S")
        processed = ""
        if video['fully_processed'] and video['processing_complete_date']:
            processed = f"Completed: {datetime.fromisoformat(video['processing_complete_date']).strftime('%Y-%m-%d %H:%M:%S')}"
        
        print(f"ID: {video['id']}")
        print(f"Title: {video['title']}")
        print(f"Status: {status}")
        print(f"Downloaded: {downloaded}")
        if processed:
            print(f"{processed}")
        print("-" * 100)

def list_segments(args):
    """List segments for a specific video."""
    if not args.video_id:
        print("Error: video-id is required.")
        return
    
    conn = sqlite3.connect(vdb.DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Verify the video exists
    cursor.execute("SELECT title FROM videos WHERE id = ?", (args.video_id,))
    video = cursor.fetchone()
    if not video:
        print(f"No video found with ID: {args.video_id}")
        conn.close()
        return
    
    cursor.execute("""
        SELECT segment_path, processed, json_output_path, processing_date
        FROM segments
        WHERE video_id = ?
        ORDER BY segment_path
    """, (args.video_id,))
    
    segments = cursor.fetchall()
    conn.close()
    
    if not segments:
        print(f"No segments found for video ID: {args.video_id}")
        return
    
    print(f"Found {len(segments)} segments for video: {video['title']} ({args.video_id})")
    print("-" * 100)
    
    for segment in segments:
        status = "✅ Processed" if segment['processed'] else "⏱️ Pending"
        processing_date = ""
        if segment['processed'] and segment['processing_date']:
            processing_date = f"Processed: {datetime.fromisoformat(segment['processing_date']).strftime('%Y-%m-%d %H:%M:%S')}"
        
        print(f"Segment: {os.path.basename(segment['segment_path'])}")
        print(f"Status: {status}")
        if segment['processed']:
            print(f"Output: {segment['json_output_path']}")
        if processing_date:
            print(f"{processing_date}")
        print("-" * 100)

def show_stats(args):
    """Show database statistics."""
    stats = vdb.get_processing_stats()
    
    print("\n=== YouTube Scraper Database Statistics ===")
    print(f"Total videos tracked: {stats['total_videos']}")
    print(f"Fully processed videos: {stats['processed_videos']}")
    print(f"Pending videos: {stats['pending_videos']}")
    
    if stats['total_videos'] > 0:
        completion_rate = (stats['processed_videos'] / stats['total_videos']) * 100
        print(f"Video completion rate: {completion_rate:.2f}%")
    
    print(f"\nTotal video segments: {stats['total_segments']}")
    print(f"Processed segments: {stats['processed_segments']}")
    print(f"Pending segments: {stats['pending_segments']}")
    
    if stats['total_segments'] > 0:
        segment_completion_rate = (stats['processed_segments'] / stats['total_segments']) * 100
        print(f"Segment completion rate: {segment_completion_rate:.2f}%")
    
    # Get additional stats
    conn = sqlite3.connect(vdb.DB_FILE)
    cursor = conn.cursor()
    
    # Get earliest and latest processing dates
    cursor.execute("SELECT MIN(downloaded_date), MAX(processing_complete_date) FROM videos WHERE fully_processed = 1")
    dates = cursor.fetchone()
    if dates[0] and dates[1]:
        print(f"\nEarliest video download: {datetime.fromisoformat(dates[0]).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Latest video processing: {datetime.fromisoformat(dates[1]).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get average segments per video
    if stats['total_videos'] > 0 and stats['total_segments'] > 0:
        avg_segments = stats['total_segments'] / stats['total_videos']
        print(f"\nAverage segments per video: {avg_segments:.2f}")
    
    conn.close()
    print("===========================================")

def reset_database(args):
    """Reset the database (with confirmation)."""
    if not args.force:
        confirm = input("WARNING: This will delete all video processing history. Are you sure? (yes/no): ")
        if confirm.lower() not in ['yes', 'y']:
            print("Database reset cancelled.")
            return
    
    if os.path.exists(vdb.DB_FILE):
        os.remove(vdb.DB_FILE)
        print(f"Database file {vdb.DB_FILE} deleted.")
    
    # Recreate the database
    vdb.initialize_database()
    print("Database has been reset.")

def mark_video(args):
    """Mark a video as processed or unprocessed."""
    if not args.video_id:
        print("Error: video-id is required.")
        return
    
    conn = sqlite3.connect(vdb.DB_FILE)
    cursor = conn.cursor()
    
    # Verify the video exists
    cursor.execute("SELECT title, fully_processed FROM videos WHERE id = ?", (args.video_id,))
    video = cursor.fetchone()
    if not video:
        print(f"No video found with ID: {args.video_id}")
        conn.close()
        return
    
    current_status = "processed" if video[1] else "unprocessed"
    new_status = args.status.lower()
    
    if current_status == new_status:
        print(f"Video is already marked as {new_status}.")
        conn.close()
        return
    
    if new_status == "processed":
        now = datetime.now().isoformat()
        cursor.execute(
            "UPDATE videos SET fully_processed = 1, processing_complete_date = ? WHERE id = ?",
            (now, args.video_id)
        )
        # Also mark all segments as processed
        cursor.execute(
            "UPDATE segments SET processed = 1, processing_date = ? WHERE video_id = ? AND processed = 0",
            (now, args.video_id)
        )
        print(f"Video ID {args.video_id} marked as processed.")
    else:
        cursor.execute(
            "UPDATE videos SET fully_processed = 0, processing_complete_date = NULL WHERE id = ?",
            (args.video_id,)
        )
        print(f"Video ID {args.video_id} marked as unprocessed.")
    
    conn.commit()
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="YouTube Scraper Database Utilities")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List videos command
    list_parser = subparsers.add_parser("list", help="List videos in the database")
    list_parser.add_argument("-p", "--processed", action="store_true", help="List only processed videos")
    list_parser.add_argument("-u", "--pending", action="store_true", help="List only pending/unprocessed videos")
    list_parser.add_argument("-l", "--limit", type=int, default=10, help="Limit the number of videos listed")
    list_parser.set_defaults(func=list_videos)
    
    # List segments command
    segments_parser = subparsers.add_parser("segments", help="List segments for a specific video")
    segments_parser.add_argument("video_id", help="Video ID to check segments for")
    segments_parser.set_defaults(func=list_segments)
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show database statistics")
    stats_parser.set_defaults(func=show_stats)
    
    # Reset command
    reset_parser = subparsers.add_parser("reset", help="Reset the database (WARNING: Deletes all data)")
    reset_parser.add_argument("-f", "--force", action="store_true", help="Force reset without confirmation")
    reset_parser.set_defaults(func=reset_database)
    
    # Mark video command
    mark_parser = subparsers.add_parser("mark", help="Mark a video as processed or unprocessed")
    mark_parser.add_argument("video_id", help="Video ID to mark")
    mark_parser.add_argument("status", choices=["processed", "unprocessed"], help="Status to set")
    mark_parser.set_defaults(func=mark_video)
    
    args = parser.parse_args()
    
    # Check if the database exists, initialize if needed
    if not os.path.exists(vdb.DB_FILE) and args.command != "reset":
        print(f"Database not found. Initializing new database.")
        vdb.initialize_database()
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 