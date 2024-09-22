from typing import Dict


class INote:

    def __init__(self, type: str) -> None:
        self.type = type

    def format(self) -> Dict[str, str]:
        raise NotImplementedError(type(self))
