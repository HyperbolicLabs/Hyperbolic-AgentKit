from collections.abc import Callable

from pydantic import BaseModel


class HyperbolicAction(BaseModel):
    """Hyperbolic Action Base Class."""

    name: str
    description: str
    args_schema: type[BaseModel] | None = None
    func: Callable[..., str]
