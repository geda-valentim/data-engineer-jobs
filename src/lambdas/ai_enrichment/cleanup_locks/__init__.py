"""CleanupLocks Lambda - EventBridge trigger for orphaned locks"""

from .handler import handler

__all__ = ["handler"]
