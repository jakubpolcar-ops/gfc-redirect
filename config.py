"""Form field mapping configuration.

Maps internal field names to JotForm widget names.
Different JotForm forms may use different widget names for the same data.
"""

from typing import TypedDict


class FieldMapping(TypedDict):
    """Mapping of internal field names to JotForm widget names."""

    parent_first: str
    parent_last: str
    child_first: str
    child_last: str


DEFAULT_FIELDS: FieldMapping = {
    "parent_first": "parent_name[first]",
    "parent_last": "parent_name[last]",
    "child_first": "kid_name[first]",
    "child_last": "kid_name[last]",
}

# Per-form overrides when a form uses different widget names
FORM_FIELDS: dict[str, FieldMapping] = {
    # Example:
    # "260433398759066": {
    #     "parent_first": "input_3[first]",
    #     "parent_last": "input_3[last]",
    #     "child_first": "input_5[first]",
    #     "child_last": "input_5[last]",
    # },
}


def get_field_mapping(jotform_id: str) -> FieldMapping:
    """Return field mapping for the given form, falling back to default."""
    return FORM_FIELDS.get(jotform_id, DEFAULT_FIELDS)
