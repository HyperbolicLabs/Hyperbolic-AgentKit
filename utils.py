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

def format_ai_message_content(content, additional_kwargs=None):
    """Format AI message content based on its type."""
    formatted_parts = []
    
    # Handle text content
    if isinstance(content, list):
        # Handle Claude-style messages
        text_parts = [f"{Colors.GREEN}{item['text']}{Colors.ENDC}" 
                     for item in content if item.get('type') == 'text' and 'text' in item]
        if text_parts:
            formatted_parts.extend(text_parts)
        tool_uses = [item for item in content if item.get('type') == 'tool_use']
        for tool_use in tool_uses:
            formatted_parts.append(f"{Colors.MAGENTA}Tool Call: {tool_use['name']}({tool_use['input']}){Colors.ENDC}")
        
    elif isinstance(content, str):
        # Handle GPT-style messages
        if content:
            formatted_parts.append(f"{Colors.GREEN}{content}{Colors.ENDC}")
        if additional_kwargs and 'tool_calls' in additional_kwargs:
            for tool_call in additional_kwargs['tool_calls']:
                formatted_parts.append(
                    f"{Colors.MAGENTA}Tool Call: {tool_call['function']['name']}({tool_call['function']['arguments']}){Colors.ENDC}"
                )    
    
    return '\n'.join(formatted_parts) if formatted_parts else str(content) 