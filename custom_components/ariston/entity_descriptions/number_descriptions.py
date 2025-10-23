"""Number entity descriptions for Ariston integration."""

from __future__ import annotations

from ariston.const import SystemType, WheType

from ..const import NAME


def create_number_descriptions() -> list[Any]:
    """Create number entity descriptions."""
    from ..const import AristonNumberEntityDescription
    
    return [
        # Basic number descriptions would go here
        # This is a simplified version for demonstration
    ]


# Create the number types list
ARISTON_NUMBER_TYPES = create_number_descriptions()











