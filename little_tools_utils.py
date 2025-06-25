"""DEPRECATED: This module has been moved to ``littletools_core.utils``.

Importing from ``little_tools_utils`` is still supported for backward compatibility
but will be removed in a future release.
"""

from importlib import import_module as _im

_utils = _im('littletools_core.utils')

globals().update({k: getattr(_utils, k) for k in _utils.__all__})

# * Expose the public API identical to the new module
__all__ = _utils.__all__  # type: ignore 