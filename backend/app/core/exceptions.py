class ToolExecutionError(Exception):
    """Raised when a registered chatbot tool cannot complete successfully."""


class QueryValidationError(ToolExecutionError):
    """Raised when SQL validation blocks a generated query."""
