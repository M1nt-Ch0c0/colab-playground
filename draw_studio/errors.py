"""Errors exposed by the Draw Studio services."""


class StateConflict(RuntimeError):
    """The current queue or workflow state prevents this operation."""


class LlmError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
