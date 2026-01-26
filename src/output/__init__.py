"""Output processing utilities."""

from .masker import (
    CommandType,
    ErrorLocation,
    MaskedOutput,
    mask_output,
)

__all__ = ["CommandType", "ErrorLocation", "MaskedOutput", "mask_output"]
