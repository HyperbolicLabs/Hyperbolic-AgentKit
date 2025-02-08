import asyncio
import logging
from typing import Any, Callable, Dict, Generic, List, TypeVar, Union, Coroutine

T = TypeVar('T')
HandlerType = Union[Callable[..., None], Callable[..., Coroutine[Any, Any, None]]]

logger = logging.getLogger(__name__)

class EventEmitter(Generic[T]):
    """Base class for components that emit events."""
    
    def __init__(self):
        self._event_handlers: Dict[T, List[HandlerType]] = {}
        
    def on(self, event: T, callback: HandlerType | None = None):
        """Register an event handler.
        
        Args:
            event: The event type to listen for
            callback: The callback function to execute when the event occurs
        """
        if callback is None:
            def decorator(f: HandlerType):
                self.on(event, f)
                return f
            return decorator
            
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(callback)
        
    def off(self, event: T, callback: HandlerType):
        """Remove an event handler.
        
        Args:
            event: The event type
            callback: The callback function to remove
        """
        if event in self._event_handlers:
            self._event_handlers[event].remove(callback)
            
    async def emit(self, event: T, *args: Any, **kwargs: Any):
        """Emit an event with optional arguments.
        
        Args:
            event: The event type to emit
            *args: Positional arguments to pass to handlers
            **kwargs: Keyword arguments to pass to handlers
        """
        if event in self._event_handlers:
            for handler in self._event_handlers[event]:
                try:
                    result = handler(*args, **kwargs)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error("Error in event handler for %s: %s", event, str(e), exc_info=True)
                    
    def clear_listeners(self, event: T | None = None):
        """Clear all event listeners for a specific event or all events.
        
        Args:
            event: Optional event type. If None, clears all listeners
        """
        if event is None:
            self._event_handlers.clear()
        elif event in self._event_handlers:
            self._event_handlers[event].clear() 