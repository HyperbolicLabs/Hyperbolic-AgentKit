#!/usr/bin/env python3
import os
import sqlite3
from datetime import datetime

# Database file path
DB_FILE = "processed_videos.db"

def initialize_database():
    """Create database and tables if they don't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create videos table to track all processed videos
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS videos (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        url TEXT NOT NULL,
        downloaded_date TEXT NOT NULL,
        fully_processed BOOLEAN NOT NULL DEFAULT 0,
        processing_complete_date TEXT
    )
    ''')
    
    # Create segments table to track all processed segments
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS segments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id TEXT NOT NULL,
        segment_path TEXT NOT NULL,
        processed BOOLEAN NOT NULL DEFAULT 0,
        json_output_path TEXT,
        processing_date TEXT,
        FOREIGN KEY (video_id) REFERENCES videos (id)
    )
    ''')
    
    conn.commit()
    conn.close()
    
    print(f"Database initialized at {DB_FILE}")

def video_exists(video_id):
    """Check if a video has already been processed."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT fully_processed FROM videos WHERE id = ?", (video_id,))
    result = cursor.fetchone()
    
    conn.close()
    
    if not result:
        return False  # Video doesn't exist in the database
    
    return result[0] == 1  # Return True if video is fully processed

def add_video(video_id, title, url):
    """Add a new video to the database when downloading starts."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Check if video already exists
    cursor.execute("SELECT id FROM videos WHERE id = ?", (video_id,))
    if cursor.fetchone():
        # Video exists but might not be fully processed, just return
        conn.close()
        return
        
    # Current date and time
    now = datetime.now().isoformat()
    
    # Insert new video
    cursor.execute(
        "INSERT INTO videos (id, title, url, downloaded_date, fully_processed) VALUES (?, ?, ?, ?, 0)",
        (video_id, title, url, now)
    )
    
    conn.commit()
    conn.close()
    
    print(f"Added video to database: {title} ({video_id})")

def add_segment(video_id, segment_path):
    """Add a video segment to the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Insert segment
    cursor.execute(
        "INSERT INTO segments (video_id, segment_path, processed) VALUES (?, ?, 0)",
        (video_id, segment_path)
    )
    
    conn.commit()
    conn.close()
    
    print(f"Added segment to database: {segment_path}")

def mark_segment_processed(segment_path, json_output_path):
    """Mark a segment as processed and store its output JSON path."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    
    # Update segment
    cursor.execute(
        "UPDATE segments SET processed = 1, json_output_path = ?, processing_date = ? WHERE segment_path = ?",
        (json_output_path, now, segment_path)
    )
    
    conn.commit()
    conn.close()
    
    print(f"Marked segment as processed: {segment_path}")

def check_video_complete(video_id):
    """Check if all segments for a video have been processed and mark video as complete if so."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Get count of all segments for this video
    cursor.execute("SELECT COUNT(*) FROM segments WHERE video_id = ?", (video_id,))
    total_segments = cursor.fetchone()[0]
    
    # Get count of processed segments
    cursor.execute("SELECT COUNT(*) FROM segments WHERE video_id = ? AND processed = 1", (video_id,))
    processed_segments = cursor.fetchone()[0]
    
    if total_segments > 0 and total_segments == processed_segments:
        now = datetime.now().isoformat()
        cursor.execute(
            "UPDATE videos SET fully_processed = 1, processing_complete_date = ? WHERE id = ?",
            (now, video_id)
        )
        conn.commit()
        print(f"Video fully processed and marked complete: {video_id}")
        result = True
    else:
        result = False
    
    conn.close()
    return result

def get_processing_stats():
    """Get statistics about processed videos."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Get total videos
    cursor.execute("SELECT COUNT(*) FROM videos")
    total_videos = cursor.fetchone()[0]
    
    # Get processed videos
    cursor.execute("SELECT COUNT(*) FROM videos WHERE fully_processed = 1")
    processed_videos = cursor.fetchone()[0]
    
    # Get total segments
    cursor.execute("SELECT COUNT(*) FROM segments")
    total_segments = cursor.fetchone()[0]
    
    # Get processed segments
    cursor.execute("SELECT COUNT(*) FROM segments WHERE processed = 1")
    processed_segments = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "total_videos": total_videos,
        "processed_videos": processed_videos,
        "pending_videos": total_videos - processed_videos,
        "total_segments": total_segments,
        "processed_segments": processed_segments,
        "pending_segments": total_segments - processed_segments
    }

def get_unprocessed_videos(limit=5):
    """Get list of videos that haven't been fully processed yet."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id, title, url FROM videos WHERE fully_processed = 0 ORDER BY downloaded_date LIMIT ?", 
        (limit,)
    )
    
    videos = [{"id": row[0], "title": row[1], "url": row[2]} for row in cursor.fetchall()]
    
    conn.close()
    
    return videos

if __name__ == "__main__":
    # Initialize the database if run directly
    initialize_database()
    
    # Print statistics if available
    stats = get_processing_stats()
    print("Database Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}") 