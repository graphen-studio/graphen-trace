"""Registry of capture adapters."""

from graphen_trace.adapters.base import CaptureAdapter
from graphen_trace.adapters.opencode import OpenCodeAdapter
from graphen_trace.adapters.pi import PiAdapter

ADAPTERS: dict[str, type[CaptureAdapter]] = {
    "opencode": OpenCodeAdapter,
    "pi": PiAdapter,
}
