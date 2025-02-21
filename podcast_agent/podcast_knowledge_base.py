import os
import sys

# Add the parent directory to PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from typing import List, Dict
import chromadb
from datetime import datetime
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import json
from utils import print_system, print_error

class PodcastSegment(BaseModel):
    id: str  # We'll generate this
    speaker: str
    content: str
    source_file: str
    timestamp: str = None  # Optional, if available in future

class PodcastKnowledgeBase:
    def __init__(self, collection_name: str = "podcast_knowledge"):
        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(path="./chroma_db")
        
        # Use the same advanced embedding model as Twitter KB
        self.embedding_model = SentenceTransformer('all-mpnet-base-v2')
        
        # Create embedding function
        class EmbeddingFunction:
            def __init__(self, model):
                self.model = model
            
            def __call__(self, input: List[str]) -> List[List[float]]:
                embeddings = self.model.encode(input)
                return embeddings.tolist()
        
        embedding_func = EmbeddingFunction(self.embedding_model)
        
        # Create or get collection
        try:
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=embedding_func
            )
        except Exception as e:
            print_error(f"Error initializing collection: {e}")
            raise

    def add_segments(self, segments: List[PodcastSegment]):
        """Add podcast segments to the knowledge base."""
        documents = [segment.content for segment in segments]
        ids = [segment.id for segment in segments]
        metadata = [
            {
                "speaker": segment.speaker,
                "source_file": segment.source_file,
                "timestamp": segment.timestamp or datetime.now().isoformat(),
            }
            for segment in segments
        ]
        
        try:
            self.collection.add(
                documents=documents,
                ids=ids,
                metadatas=metadata
            )
            print_system(f"Added {len(segments)} segments to knowledge base")
        except Exception as e:
            print_error(f"Error adding segments: {e}")

    def process_json_file(self, file_path: str):
        """Process a podcast transcript JSON file and add it to the knowledge base."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                transcript_data = json.load(f)
            
            segments = []
            for idx, entry in enumerate(transcript_data):
                segment = PodcastSegment(
                    id=f"{os.path.basename(file_path)}_{idx}",
                    speaker=entry['speaker'],
                    content=entry['content'],
                    source_file=file_path
                )
                segments.append(segment)
            
            self.add_segments(segments)
            print_system(f"Successfully processed {file_path}")
            return True
            
        except Exception as e:
            print_error(f"Error processing {file_path}: {e}")
            return False

    def query_knowledge_base(self, query: str, n_results: int = 5) -> List[Dict]:
        """Query the knowledge base for relevant podcast segments."""
        try:
            print_system(f"Querying knowledge base with: {query}")
            
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            if not results['documents'][0]:
                print_system("No results found in knowledge base")
                return []
                
            formatted_results = []
            for doc, metadata, distance in zip(
                results['documents'][0], 
                results['metadatas'][0],
                results['distances'][0]
            ):
                formatted_results.append({
                    "content": doc,
                    "metadata": metadata,
                    "relevance_score": 1 - distance
                })
            
            # Sort by relevance score
            formatted_results.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            print_system(f"Found {len(formatted_results)} relevant segments")
            return formatted_results
            
        except Exception as e:
            print_error(f"Error querying knowledge base: {e}")
            return []

    def format_query_results(self, results: List[Dict]) -> str:
        """Format query results into a readable string."""
        if not results:
            return "No relevant podcast segments found."
            
        formatted_output = []
        for result in results:
            formatted_output.append(
                f"Speaker: {result['metadata']['speaker']}\n"
                f"Source: {os.path.basename(result['metadata']['source_file'])}\n"
                f"Relevance: {result['relevance_score']:.2f}\n"
                f"Content: {result['content']}\n"
            )
            
        return "\n---\n".join(formatted_output)

    def clear_collection(self) -> bool:
        """Clear all segments from the knowledge base."""
        try:
            print_system("Clearing knowledge base collection...")
            ids = self.collection.get()["ids"]
            if ids:
                self.collection.delete(ids=ids)
                print_system("Knowledge base cleared successfully")
            else:
                print_system("Knowledge base is already empty")
            return True
        except Exception as e:
            print_error(f"Error clearing knowledge base: {str(e)}")
            return False

    def get_processed_files(self) -> set:
        """Get a set of already processed file names from the metadata."""
        try:
            metadata = self.collection.get()
            if not metadata.get("metadatas"):
                return set()
            return {os.path.basename(m["source_file"]) for m in metadata["metadatas"]}
        except Exception as e:
            print_error(f"Error getting processed files: {e}")
            return set()

    def process_all_json_files(self, directory: str = "jsonoutputs"):
        """Process all JSON files in the specified directory, skipping already processed ones."""
        try:
            # Convert to absolute path relative to the project root
            abs_directory = os.path.join(parent_dir, directory)
            
            if not os.path.exists(abs_directory):
                print_error(f"Directory not found: {abs_directory}")
                return
            
            # Get list of all JSON files and already processed files
            json_files = [f for f in os.listdir(abs_directory) if f.endswith('.json')]
            processed_files = self.get_processed_files()
            
            # Filter out already processed files
            new_files = [f for f in json_files if f not in processed_files]
            
            if not new_files:
                print_system("No new JSON files to process")
                return
            
            print_system(f"Found {len(new_files)} new JSON files to process")
            
            for json_file in new_files:
                file_path = os.path.join(abs_directory, json_file)
                self.process_json_file(file_path)
                
            print_system("Finished processing all new JSON files")
            
        except Exception as e:
            print_error(f"Error processing JSON files: {e}")

    def get_collection_stats(self) -> Dict:
        """Get statistics about the knowledge base collection."""
        try:
            count = self.collection.count()
            metadata = self.collection.get()
            last_update = None
            if metadata.get("metadatas"):
                # Get most recent timestamp
                last_update = max(m["timestamp"] for m in metadata["metadatas"])
                last_update = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
            
            print_system(f"Podcast knowledge base contains {count} segments")
            return {
                "count": count,
                "last_update": last_update or datetime.now()
            }
        except Exception as e:
            print_error(f"Error getting collection stats: {str(e)}")
            return {"count": 0, "last_update": datetime.now()}

def main():
    # Initialize the knowledge base
    kb = PodcastKnowledgeBase()

    # Process all JSON files in the directory
    kb.process_all_json_files()

    # Example queries to test the knowledge base
    test_queries = [
        "What did Jeff say about Ronin's user base?",
        "What are the key lessons learned from Axie Infinity?",
        "How many daily active users does Ronin have?",
    ]

    # Run each test query
    for query in test_queries:
        print("\n" + "="*50)
        print(f"Query: {query}")
        print("="*50)
        
        results = kb.query_knowledge_base(query)
        print(kb.format_query_results(results))

if __name__ == "__main__":
    main()
