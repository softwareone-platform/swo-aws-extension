from dataclasses import dataclass
from datetime import date


@dataclass
class Context:

    def __str__(self):
        return f"Context"