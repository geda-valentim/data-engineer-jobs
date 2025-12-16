"""InvokeEnrichment Lambda - receives SQS, starts Step Function"""

from .handler import handler

__all__ = ["handler"]
