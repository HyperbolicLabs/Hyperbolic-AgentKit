import os
import sys

# Add the parent directory to PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from typing import List, Dict
from datetime import datetime
from pydantic import BaseModel
import json
from utils import print_system, print_error
from pymilvus import MilvusClient, model
from sentence_transformers import SentenceTransformer

class PodcastSegment(BaseModel):
    id: str  # We'll generate this
    speaker: str
    content: str
    source_file: str
    timestamp: str = None  # Optional, if available in future

class PodcastKnowledgeBase:
    def __init__(self, collection_name: str = "podcast_knowledge"):
        # Initialize Milvus client
        self.client = MilvusClient("podcast_kb.db")
        self.collection_name = collection_name
        
        print_system("Loading sentence-transformer model...")
        # Initialize sentence transformer model
        self.model = SentenceTransformer('all-mpnet-base-v2')
        print_system("Model loaded successfully")
        
        # Create or get collection
        try:
            if not self.client.has_collection(collection_name=self.collection_name):
                self.client.create_collection(
                    collection_name=self.collection_name,
                    dimension=768,  # MPNet dimension
                    metric_type="COSINE"  # Use COSINE similarity for better semantic matching
                )
                print_system(f"Created new collection: {self.collection_name}")
            else:
                print_system(f"Using existing collection: {self.collection_name}")
        except Exception as e:
            print_error(f"Error initializing collection: {e}")
            raise

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings using sentence-transformers."""
        try:
            # Process texts in batches to avoid memory issues
            embeddings = self.model.encode(
                texts,
                batch_size=32,
                show_progress_bar=True,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
            return embeddings.tolist()
        except Exception as e:
            print_error(f"Error generating embeddings: {e}")
            print_error(f"Full error details: {str(e)}")
            raise

    def add_segments(self, segments: List[PodcastSegment]):
        """Add podcast segments to the knowledge base."""
        try:
            # Get embeddings for all segments
            texts = [segment.content for segment in segments]
            vectors = self._get_embeddings(texts)
            
            data = [
                {
                    "id": i,
                    "vector": vectors[i],
                    "content": segment.content,
                    "speaker": segment.speaker,
                    "source_file": segment.source_file,
                    "timestamp": segment.timestamp or datetime.now().isoformat()
                }
                for i, segment in enumerate(segments)
            ]
            
            # Insert data into Milvus
            self.client.insert(
                collection_name=self.collection_name,
                data=data
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
            
            # Get query embedding
            query_vector = self.model.encode(
                query,
                convert_to_numpy=True,
                normalize_embeddings=True
            ).tolist()
            
            print_system(f"Generated embedding of dimension: {len(query_vector)}")
            
            # Search in Milvus with optimized retrieval settings
            print_system(f"Searching with limit={n_results}")
            results = self.client.search(
                collection_name=self.collection_name,
                data=[query_vector],
                limit=n_results,
                output_fields=["content", "speaker", "source_file", "timestamp"],
                search_params={
                    "metric_type": "COSINE",
                    "params": {"nprobe": 10}  # Increase search scope
                }
            )
            
            # More detailed debug logging
            if results and results[0]:
                print_system(f"Raw results count: {len(results[0])}")
                print_system(f"First result distance: {results[0][0]['distance'] if results[0] else 'N/A'}")
                distances = [hit['distance'] for hit in results[0]]
                print_system(f"All distances: {distances}")
            
            if not results or not results[0]:  # Check both results and first query results
                print_system("No results found in knowledge base")
                return []
            
            # Format results - results[0] contains hits for the first query
            formatted_results = []
            for i, hit in enumerate(results[0]):
                try:
                    formatted_results.append({
                        "content": hit["entity"]["content"],
                        "metadata": {
                            "speaker": hit["entity"]["speaker"],
                            "source_file": hit["entity"]["source_file"],
                            "timestamp": hit["entity"]["timestamp"]
                        },
                        "relevance_score": hit["distance"]  # Use distance directly
                    })
                except Exception as e:
                    print_error(f"Error processing hit {i}: {e}")
                    continue
            
            # Sort by distance (lowest first since lower distance = more similar)
            formatted_results.sort(key=lambda x: x['relevance_score'])
            
            print_system(f"Found {len(formatted_results)} relevant segments")
            return formatted_results
            
        except Exception as e:
            print_error(f"Error querying knowledge base: {e}")
            print_error(f"Full error details: {str(e)}")
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
            if self.client.has_collection(collection_name=self.collection_name):
                self.client.drop_collection(collection_name=self.collection_name)
                # Recreate the collection
                self.client.create_collection(
                    collection_name=self.collection_name,
                    dimension=768
                )
                print_system("Knowledge base cleared successfully")
            else:
                print_system("Knowledge base is already empty")
            return True
        except Exception as e:
            print_error(f"Error clearing knowledge base: {str(e)}")
            return False

    def process_all_json_files(self, directory: str = "jsonoutputs"):
        """Process all JSON files in the specified directory."""
        try:
            # Convert to absolute path relative to the project root
            abs_directory = os.path.join(parent_dir, directory)
            
            if not os.path.exists(abs_directory):
                print_error(f"Directory not found: {abs_directory}")
                return
            
            json_files = [f for f in os.listdir(abs_directory) if f.endswith('.json')]
            if not json_files:
                print_system(f"No JSON files found in {abs_directory}")
                return
            
            print_system(f"Found {len(json_files)} JSON files to process")
            
            for json_file in json_files:
                file_path = os.path.join(abs_directory, json_file)
                self.process_json_file(file_path)
                
            print_system("Finished processing all JSON files")
            
        except Exception as e:
            print_error(f"Error processing JSON files: {e}")

    def get_collection_stats(self) -> Dict:
        """Get statistics about the knowledge base collection."""
        try:
            count = self.client.query(
                collection_name=self.collection_name,
                filter="",
                output_fields=["timestamp"],
                limit=1
            )
            last_update = None
            if count:
                timestamps = [datetime.fromisoformat(hit.get("timestamp").replace('Z', '+00:00')) 
                            for hit in count if hit.get("timestamp")]
                if timestamps:
                    last_update = max(timestamps)
            
            print_system(f"Podcast knowledge base contains {len(count)} segments")
            return {
                "count": len(count),
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
