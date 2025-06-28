"""MCP Trading Memory - Tools for managing trading memory and preventing LLM trading amnesia."""

__version__ = "0.1.0"

# Lazy import to avoid dependency issues during development
def get_app():
    """Get the FastMCP app instance."""
    from src.server import app
    return app

__all__ = ["get_app"]