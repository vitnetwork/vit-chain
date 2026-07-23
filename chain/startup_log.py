"""chain/startup_log.py — module-level dict for startup error capture."""
import traceback as _tb

errors: dict = {}


def capture(key: str, exc: Exception) -> None:
    """Call from an except block to record the import error."""
    errors[key] = {
        "error": str(exc),
        "type": type(exc).__name__,
        "tb": _tb.format_exc(),
    }
