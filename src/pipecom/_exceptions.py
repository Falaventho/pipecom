class PipeError(Exception):
    """Custom exception for pipe-related errors.

    Attributes:
        error_code: A code identifying the type of error
        message: Human-readable error message
        context: Optional additional context about the error
    """

    # Common error codes
    INVALID_PIPE = "INVALID_PIPE"
    INVALID_PIPE_NAME = "INVALID_PIPE_NAME"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"
    DEBUG = "DEBUG"

    def __init__(self, message: str, error_code: str, context=None):
        """Initialize PipeError.

        Args:
            message (str): Human-readable error message
            error_code (str): Error code identifying the error type
            context (dict, optional): Additional context about the error
        """
        self.error_code = error_code
        self.context = context or {}
        super().__init__(message)

    def __str__(self):
        """Return string representation of the error."""
        base_msg = f"PipeError (Code: {self.error_code}): {super().__str__()}"
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{base_msg} [Context: {context_str}]"
        return base_msg

    def __repr__(self):
        """Return detailed representation for debugging."""
        return f"PipeError(message={super().__str__()!r}, error_code={self.error_code!r}, context={self.context!r})"

    def to_dict(self):
        """Convert error to dictionary for serialization."""
        return {
            "error_type": "PipeError",
            "message": str(super()),
            "error_code": self.error_code,
            "context": self.context
        }
