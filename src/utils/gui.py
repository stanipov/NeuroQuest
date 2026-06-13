"""
GUI utility functions for formatting and display
"""

from typing import Dict, List, Union


def format_dict_with_categories(
    data: Dict[str, Union[List[str], str, Dict]], indent_level: int = 2
) -> str:
    """
    Format a dictionary of categories and items with plain text headers.

    This function converts structured data (like world rules or NPC behavioral rules)
    into a formatted plain text string for displaying in console panels.

    Args:
        data: Dictionary mapping category names to lists of string items, strings, or nested dicts
        indent_level: Number of spaces for base indentation (default 2).
                     Each nested level increases by this amount.

    Returns:
        Plain text formatted string with category headers and indented bullet points

    Example:
        >>> data = {"MAGIC": ["Rule 1", "Rule 2"], "PHYSICS": []}
        >>> format_dict_with_categories(data)
        'MAGIC\\n  • Rule 1\\n  • Rule 2\\nPHYSICS\\n  No values available'

    Empty Handling:
        - Empty lists [] display as "No values available" under the category header
        - None or missing data returns "No data available"

    Formatting Rules:
        - Category names keep original case (no .title() conversion)
        - No blank lines between categories (compact display)
        - Each nested level increases indent by indent_level spaces
        - Uses Unicode bullet character (•) for list items
    """
    if not data:
        return "No data available"

    lines = []

    for category, items in data.items():
        # Bold category header using Rich markup (keep original case)
        lines.append(f"{category}")

        if isinstance(items, list):
            if len(items) == 0:
                # Empty list - show message with indent
                lines.append(f"{' ' * indent_level}No values available")
            else:
                # List of items - use bullet points
                for item in items:
                    lines.append(f"{' ' * indent_level}• {item}")

        elif isinstance(items, str):
            # Single string item
            lines.append(f"{' ' * indent_level}• {items}")

        elif isinstance(items, dict):
            # Nested dictionary - recurse with increased indent
            nested = format_dict_with_categories(items, indent_level + 2)
            lines.append(f"\n{nested}")

        else:
            # Fallback for other types
            lines.append(f"{' ' * indent_level}• {str(items)}")

        # No blank line between categories (compact display)

    return "\n".join(lines).rstrip()  # Remove trailing newline
