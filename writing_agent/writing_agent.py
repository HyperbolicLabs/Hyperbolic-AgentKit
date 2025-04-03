import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import traceback
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

# Add the root directory to Python path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from llm_provider import get_llm
from base_utils.utils import print_system, print_error
from writing_agent.web_searcher import WebSearcher
from writing_agent.document_sender import DocumentSender

class WritingAgent:
    """Main agent for writing content with research and style adaptation."""
    
    # Standard directory for reference documents
    REFERENCE_DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reference_docs")
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the writing agent.
        
        Args:
            api_key: Optional API key for the language model (can be either MIRA or Anthropic API key)
        """
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.mira_api_key = api_key or os.environ.get("MIRA_API_KEY")
        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        
        if not self.mira_api_key and not self.anthropic_api_key:
            self.logger.warning("No API keys provided. API-dependent features will not work.")
        else:
            provider = "Mira" if self.mira_api_key else "Anthropic"
            self.logger.info(f"{provider} API key found and set successfully")
        
        self.searcher = WebSearcher()
        self.logger.info("Web searcher initialized")
        
        # Initialize document sender for direct document integration
        # Pass the appropriate API key to document sender
        self.document_sender = DocumentSender(api_key=self.anthropic_api_key)  # Document sender still uses Anthropic
        self.logger.info("Document sender initialized")
        
        # Initialize reference tracking
        self.reference_materials = []
        
        # Initialize language model
        self.llm = get_llm(
            api_key=self.mira_api_key,  # Will use Mira if available (with fixed model)
            anthropic_api_key=self.anthropic_api_key,  # Will fall back to Anthropic if needed
            model="claude-3-5-sonnet-20240620"  # Only used if falling back to Anthropic
        )
        self.logger.info("Language model initialized")
        
        # Initialize default article parameters
        self.target_length = 1500  # words
        
    async def load_reference_materials(self, file_paths: List[str] = None) -> bool:
        """
        Load reference materials for future queries.
        If no file paths are provided, loads all documents from the standard reference_docs directory.
        
        Args:
            file_paths: List of file paths to process (optional)
            
        Returns:
            True if successful, False otherwise
        """
        self.logger.info("Starting to load reference materials")
        
        # If no paths provided, use all files from the reference_docs directory
        if file_paths is None:
            self.logger.info(f"No file paths provided, checking reference directory: {self.REFERENCE_DOCS_DIR}")
            if os.path.exists(self.REFERENCE_DOCS_DIR):
                file_paths = []
                for filename in os.listdir(self.REFERENCE_DOCS_DIR):
                    file_path = os.path.join(self.REFERENCE_DOCS_DIR, filename)
                    if os.path.isfile(file_path) and not filename.startswith('.'):
                        file_paths.append(file_path)
                self.logger.info(f"Found {len(file_paths)} documents in reference directory")
            else:
                self.logger.error(f"Reference documents directory not found: {self.REFERENCE_DOCS_DIR}")
                return False
        
        if not file_paths:
            self.logger.error("No reference materials provided")
            return False
            
        self.logger.info(f"Loading {len(file_paths)} reference materials...")
        
        # Store the file paths for later use with direct document sending
        self.reference_materials = file_paths
        self.logger.info(f"Reference materials loaded: {[os.path.basename(f) for f in file_paths]}")
        return True
    
    async def create_content(self, topic: str, target_length: Optional[int] = None, output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Create content on a given topic with research and style adaptation.
        
        Args:
            topic: The topic or subject to write about
            target_length: Target length of the article in words (optional)
            output_file: Optional path to save the output text
            
        Returns:
            Dictionary containing content, word count, sources
        """
        self.logger.info(f"Creating content about: {topic}")
        if target_length:
            self.logger.info(f"Target length set to: {target_length} words")
            self.target_length = target_length
        
        try:
            # Research the topic
            self.logger.info(f"Starting research phase for topic: {topic}")
            research_results = await self.research_topic(topic)
            
            if not research_results:
                self.logger.error("Research failed. Cannot proceed with content creation.")
                return {
                    "content": "Error occurred during research phase.",
                    "word_count": 0,
                    "sources": []
                }
            
            self.logger.info("Research completed successfully")
            
            # Create the content generation prompt
            self.logger.info("Creating content generation prompt")
            content_prompt = self._create_content_prompt(topic, research_results)
            self.logger.info(f"Prompt created with {len(content_prompt)} characters")
            
            # Check reference materials
            if not self.reference_materials:
                self.logger.warning("No reference materials loaded for style mimicry")
            else:
                self.logger.info(f"Using {len(self.reference_materials)} reference materials for style mimicry")
            
            # Generate content using document sender
            self.logger.info("Sending query to document sender")
            content = await self.document_sender.send_query_with_documents(
                query=content_prompt,
                file_paths=self.reference_materials,
                max_tokens=4096,
                output_file=output_file
            )
            
            if not content:
                self.logger.error("Content generation failed")
                return {
                    "content": "Content generation failed. Please try again.",
                    "word_count": 0,
                    "sources": self._extract_sources(research_results)
                }
            
            # Count words
            word_count = len(content.split())
            self.logger.info(f"Generated content with {word_count} words")
            
            # Extract sources
            sources = self._extract_sources(research_results)
            self.logger.info(f"Extracted {len(sources)} sources")
            
            return {
                "content": content,
                "word_count": word_count,
                "sources": sources
            }
            
        except Exception as e:
            self.logger.error(f"Error creating content: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return {
                "content": f"Error occurred during content creation: {str(e)}",
                "word_count": 0,
                "sources": []
            }
    
    async def research_topic(self, topic: str) -> Dict[str, Any]:
        """
        Research a topic using web search.
        
        Args:
            topic: The topic to research
            
        Returns:
            Dictionary with research results
        """
        self.logger.info(f"Starting research for topic: {topic}")
        
        try:
            # Search the web
            self.logger.info("Initiating web search")
            web_results = await self.searcher.search(topic, num_results=10)
            self.logger.info(f"Retrieved {len(web_results)} web results")
            
            # Format results in a standard structure
            self.logger.info("Formatting web results")
            formatted_web_results = []
            for result in web_results:
                if hasattr(result, 'to_dict'):
                    formatted_web_results.append(result.to_dict())
                elif isinstance(result, dict):
                    formatted_web_results.append(result)
                else:
                    formatted_web_results.append({
                        "title": getattr(result, "title", "Unknown"),
                        "content": getattr(result, "content", str(result)[:500]),
                        "url": getattr(result, "url", ""),
                        "source_type": "web"
                    })
            
            # Combine results
            results = {
                "web_results": formatted_web_results,
                "sources": [r.get("url", "") for r in formatted_web_results if r.get("url")],
                "summary": f"Found {len(web_results)} web resources for '{topic}'"
            }
            
            self.logger.info(f"Research complete. Found {len(web_results)} web resources")
            return results
            
        except Exception as e:
            self.logger.error(f"Error during research: {e}")
            return {
                "web_results": [],
                "sources": [],
                "summary": f"Research error: {str(e)}"
            }
    
    def _create_content_prompt(self, topic: str, research: Dict[str, Any]) -> str:
        """Create a prompt for content generation."""
        self.logger.info("Creating content generation prompt")
        
        prompt = f"""Write a comprehensive article about: {topic}

Target length: {self.target_length} words

Use these research sources for accurate information:
"""
        
        # Add research sources
        source_count = 0
        for result in research.get("web_results", []):
            prompt += f"\n- {result.get('title', 'Unknown')}: {result.get('content', '')[:200]}..."
            source_count += 1
            
        self.logger.info(f"Added {source_count} sources to prompt")
        
        prompt += "\n\nRequirements:"
        prompt += "\n1. Write in a clear, engaging style"
        prompt += "\n2. Include relevant citations from the sources"
        prompt += "\n3. Organize content logically with clear sections"
        prompt += "\n4. Aim for the target length"
        prompt += "\n5. Include a references section at the end"
        
        self.logger.info(f"Final prompt length: {len(prompt)} characters")
        return prompt
    
    def _extract_sources(self, research: Dict[str, Any]) -> List[str]:
        """Extract source URLs from research results."""
        sources = research.get("sources", [])
        self.logger.info(f"Extracted {len(sources)} sources from research results")
        return sources 