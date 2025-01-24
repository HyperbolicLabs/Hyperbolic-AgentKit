import sqlite3
import os
from datetime import datetime, timedelta
import json

# Constants
MENTION_CHECK_INTERVAL = 2 * 60  
MAX_MENTIONS_PER_INTERVAL = 50  # Adjust based on your API tier limits

class TwitterState:
    def __init__(self):
        self.account_id = None
        self.last_mention_id = None
        self.last_check_time = None
        self.mentions_count = 0
        self.reset_time = None
        # Get character name from env and create DB name
        self.db_name = self._get_db_name()
        self._init_db()
        
    def _get_db_name(self):
        """Generate database name based on character file."""
        character_file = os.getenv('CHARACTER_FILE')
        if not character_file:
            return 'twitter_state.db'  # fallback to default
        
        try:
            # Extract filename without extension
            char_name = os.path.splitext(os.path.basename(character_file))[0]
            return f'twitter_state_{char_name}.db'
        except Exception:
            return 'twitter_state.db'  # fallback to default

    def _init_db(self):
        """Initialize SQLite database for state and replied tweets."""
        with sqlite3.connect(self.db_name) as conn:
            # Create replied tweets table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS replied_tweets (
                    tweet_id TEXT PRIMARY KEY,
                    replied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create reposted tweets table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS reposted_tweets (
                    tweet_id TEXT PRIMARY KEY,
                    reposted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create state table for other Twitter state data
            conn.execute('''
                CREATE TABLE IF NOT EXISTS twitter_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            conn.execute('CREATE INDEX IF NOT EXISTS idx_replied_at ON replied_tweets(replied_at)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_reposted_at ON reposted_tweets(reposted_at)')
    
    def load(self):
        """Load state from SQLite database."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.execute('SELECT key, value FROM twitter_state')
            for key, value in cursor.fetchall():
                if key == 'last_mention_id':
                    self.last_mention_id = value
                elif key == 'last_check_time':
                    self.last_check_time = datetime.fromisoformat(value) if value else None
                elif key == 'reset_time':
                    self.reset_time = datetime.fromisoformat(value) if value else None
                elif key == 'mentions_count':
                    self.mentions_count = int(value)

    def save(self):
        """Save state to SQLite database."""
        with sqlite3.connect(self.db_name) as conn:
            state_data = {
                'last_mention_id': self.last_mention_id,
                'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
                'mentions_count': str(self.mentions_count),
                'reset_time': self.reset_time.isoformat() if self.reset_time else None
            }
            
            for key, value in state_data.items():
                conn.execute('''
                    INSERT OR REPLACE INTO twitter_state (key, value) 
                    VALUES (?, ?)
                ''', (key, value))
            conn.commit()
  

    def add_replied_tweet(self, tweet_id):
        """Add a tweet ID to the database of replied tweets."""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute('INSERT OR REPLACE INTO replied_tweets (tweet_id) VALUES (?)', (tweet_id,))
                conn.commit()
            return f"Successfully added tweet {tweet_id} to replied tweets database"
        except Exception as e:
            return f"Error adding tweet {tweet_id} to database: {str(e)}"

    def has_replied_to(self, tweet_id):
        """Check if we've already replied to this tweet."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.execute('SELECT 1 FROM replied_tweets WHERE tweet_id = ?', (tweet_id,))
            return cursor.fetchone() is not None

    def can_check_mentions(self):
        """Check if enough time has passed since last mention check."""
        if not self.last_check_time:
     
            return True
        
        time_since_last_check = (datetime.now() - self.last_check_time).total_seconds()
      
        return time_since_last_check >= MENTION_CHECK_INTERVAL

    def update_rate_limit(self):
        """Update and check rate limits."""
        now = datetime.now()
        if not self.reset_time or now >= self.reset_time:
            self.mentions_count = 0
            self.reset_time = now + timedelta(minutes=15)
        
        self.mentions_count += 1
        return self.mentions_count <= MAX_MENTIONS_PER_INTERVAL 

    def add_reposted_tweet(self, tweet_id: str) -> str:
        """Add a tweet ID to the database of reposted tweets."""
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute(
                    'INSERT INTO reposted_tweets (tweet_id) VALUES (?)',
                    (tweet_id,)
                )
            return f"Successfully recorded repost of tweet {tweet_id}"
        except sqlite3.IntegrityError:
            return f"Tweet {tweet_id} was already recorded as reposted"

    def has_reposted(self, tweet_id: str) -> bool:
        """Check if we have already reposted a tweet."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.execute(
                'SELECT 1 FROM reposted_tweets WHERE tweet_id = ?',
                (tweet_id,)
            )
            return cursor.fetchone() is not None 