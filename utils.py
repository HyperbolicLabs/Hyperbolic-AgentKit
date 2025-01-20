import threading
import time

# ANSI color codes
class Colors:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"

def print_ai(text):
    """Print AI responses in green."""
    print(f"{Colors.GREEN}{text}{Colors.ENDC}")

def print_system(text):
    """Print system messages in yellow."""
    print(f"{Colors.YELLOW}{text}{Colors.ENDC}")

def print_error(text):
    """Print error messages in red."""
    print(f"{Colors.RED}{text}{Colors.ENDC}")

class ProgressIndicator:
    def __init__(self):
        self.animation = "▁▂▃▄▅▆▇█▇▆▅▄▃▂▁"
        self.idx = 0
        self._stop_event = threading.Event()
        self._thread = None
        
    def _animate(self):
        """Animation loop running in separate thread."""
        while not self._stop_event.is_set():
            print(f"\r{Colors.YELLOW}Processing {self.animation[self.idx]}{Colors.ENDC}", end="", flush=True)
            self.idx = (self.idx + 1) % len(self.animation)
            time.sleep(0.2)  # Update every 0.2 seconds
            
    def start(self):
        """Start the progress animation in a separate thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._animate)
        self._thread.daemon = True
        self._thread.start()
        
    def stop(self):
        """Stop the progress animation."""
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join()
            print("\r" + " " * 50 + "\r", end="", flush=True)  # Clear the line

def run_with_progress(func, *args, **kwargs):
    """Run a function while showing a progress indicator."""
    progress = ProgressIndicator()
    
    try:
        progress.start()
        generator = func(*args, **kwargs)
        chunks = []
        
        for chunk in generator:
            progress.stop()
            
            if "agent" in chunk:
                print(f"\n{Colors.GREEN}{chunk['agent']['messages'][0].content}{Colors.ENDC}")
            elif "tools" in chunk:
                print(f"\n{Colors.YELLOW}{chunk['tools']['messages'][0].content}{Colors.ENDC}")
            print(f"\n{Colors.YELLOW}-------------------{Colors.ENDC}")
            
            chunks.append(chunk)
            progress.start()
        
        return chunks
    finally:
        progress.stop()

def format_ai_message_content(content, additional_kwargs=None, format_mode="ansi"):
    """Format AI message content based on its type and format mode.
    
    Args:
        content: The content to format
        additional_kwargs: Additional keyword arguments
        format_mode: Either "ansi" for terminal, or "markdown" for gradio display
    """
    formatted_parts = []
    
    # Define color formats for different modes
    colors = {
        "ansi": {
            "green": Colors.GREEN,
            "magenta": Colors.MAGENTA,
            "end": Colors.ENDC
        },
        "markdown": {
            "green": '<span style="color: #2ecc71">',  # Bright green
            "magenta": '<span style="color: #e056fd">',  # Bright magenta
            "end": '</span>'
        }
    }
    
    # Get the appropriate color set
    color_set = colors[format_mode]
    
    # Handle text content
    if isinstance(content, list):
        # Handle Claude-style messages
        text_parts = [
            f"{color_set['green']}{item['text']}{color_set['end']}"
            for item in content if item.get('type') == 'text' and 'text' in item
        ]
        if text_parts:
            if format_mode == "markdown":
                # Process each text part individually since text_parts is a list
                processed_parts = []
                for part in text_parts:
                    processed = part.replace("<response_planning>", "**Planning:**\n")
                    processed = processed.replace("</response_planning>", "\n") 
                    processed = processed.replace("<response>", "**Response:**\n")
                    processed = processed.replace("</response>", "")
                    processed_parts.append(processed)
                formatted_parts.extend(processed_parts)
            else:
                formatted_parts.extend(text_parts)
        
        tool_uses = [item for item in content if item.get('type') == 'tool_use']
        for tool_use in tool_uses:
            formatted_parts.append(
                f"{color_set['magenta']}Tool Call: {tool_use['name']}({tool_use['input']}){color_set['end']}"
            )
        
    elif isinstance(content, str):
        # Handle GPT-style messages
        if content:
            # Clean up XML-like tags if in markdown mode
            if format_mode == "markdown":
                content = content.replace("<response_planning>", "**Planning:**\n")
                content = content.replace("</response_planning>", "\n")
                content = content.replace("<response>", "**Response:**\n")
                content = content.replace("</response>", "")
            formatted_parts.append(f"{color_set['green']}{content}{color_set['end']}")
            
        if additional_kwargs and 'tool_calls' in additional_kwargs:
            for tool_call in additional_kwargs['tool_calls']:
                formatted_parts.append(
                    f"{color_set['magenta']}Tool Call: {tool_call['function']['name']}({tool_call['function']['arguments']}){color_set['end']}"
                )    
    
    return '\n'.join(formatted_parts) if formatted_parts else str(content) 