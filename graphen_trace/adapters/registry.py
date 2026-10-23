"""Registry of capture adapters."""

from graphen_trace.adapters.opencode import OpenCodeAdapter
from graphen_trace.adapters.pi import PiAdapter

ADAPTERS = {"opencode": OpenCodeAdapter, "pi": PiAdapter}
