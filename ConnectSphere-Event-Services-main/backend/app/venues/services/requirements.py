"""
Venue Suitability Check — fixed requirement vocabularies
--------------------------------------------------------
Story 2 is deliberately bounded to a FIXED list of accessibility features and
layout types (adding new requirement types is out of scope). Event requests
store these codes. Venue records (Venue Catalogue) store free-text names typed
by Venue Staff, so venue_accessibility_codes() / venue_layout_codes() map those
names onto the same codes; names that match nothing are simply not counted.

The free-text `events.accessibility_needs` field is untouched and still
required on submission; it is shown to Coordinators as context but is not
checked automatically.
"""

ACCESSIBILITY_FEATURES = {
    "step_free_access": "Step-free access",
    "hearing_loop": "Hearing loop",
    "accessible_toilet": "Accessible toilet nearby",
    "wheelchair_seating": "Wheelchair seating spaces",
    "accessible_parking": "Accessible parking",
}

LAYOUT_TYPES = {
    "theatre": "Theatre",
    "classroom": "Classroom",
    "boardroom": "Boardroom",
    "u_shape": "U-shape",
    "banquet": "Banquet",
    "cabaret": "Cabaret",
    "reception": "Reception",
    "exhibition": "Exhibition",  # one of the Venue Catalogue's standard layouts
}

# Existing event requests store required_layout as free text (e.g. "Theater",
# "U shape"), so we normalise common spellings onto the fixed codes.
_LAYOUT_ALIASES = {
    "theater": "theatre",
    "ushape": "u_shape",
    "u": "u_shape",
    "horseshoe": "u_shape",
    "board_room": "boardroom",
    "class_room": "classroom",
    "standing": "reception",
}


def normalise_layout(value):
    """Maps free-text layout input onto a LAYOUT_TYPES code, or None if the
    value is blank or not a recognised layout."""
    if value is None:
        return None
    key = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if not key:
        return None
    key = _LAYOUT_ALIASES.get(key, key)
    key = _LAYOUT_ALIASES.get(key.replace("_", ""), key)
    return key if key in LAYOUT_TYPES else None


def layout_label(code):
    return LAYOUT_TYPES.get(code, code)


def accessibility_label(code):
    return ACCESSIBILITY_FEATURES.get(code, code)


def clean_accessibility_codes(values):
    """De-duplicates and trims a list of accessibility codes, keeping order.
    Unknown codes are kept so submission validation can report them."""
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    seen, cleaned = set(), []
    for v in values:
        code = str(v).strip().lower()
        if code and code not in seen:
            seen.add(code)
            cleaned.append(code)
    return cleaned


# Common ways Venue Staff may write each accessibility feature in the Venue
# Catalogue (free text). Matching is case/punctuation-insensitive.
_ACCESSIBILITY_ALIASES = {
    "step_free_access": ("step free", "stepfree", "step free access", "ramp", "ramps",
                         "wheelchair access", "wheelchair accessible", "lift", "lifts",
                         "elevator", "level access"),
    "hearing_loop": ("hearing loop", "induction loop", "audio induction loop", "loop system"),
    "accessible_toilet": ("accessible toilet", "accessible toilets", "accessible restroom",
                          "accessible washroom", "disabled toilet", "accessible toilet nearby"),
    "wheelchair_seating": ("wheelchair seating", "wheelchair spaces", "wheelchair seating spaces",
                           "wheelchair space"),
    "accessible_parking": ("accessible parking", "disabled parking", "accessible car park"),
}


def _simplify(text):
    return " ".join("".join(ch if ch.isalnum() else " " for ch in str(text).lower()).split())


_NAME_TO_CODE = {}
for _code, _label in ACCESSIBILITY_FEATURES.items():
    _NAME_TO_CODE[_simplify(_code)] = _code
    _NAME_TO_CODE[_simplify(_label)] = _code
    for _alias in _ACCESSIBILITY_ALIASES.get(_code, ()):
        _NAME_TO_CODE[_simplify(_alias)] = _code


def accessibility_code_for(name):
    """Fixed code for a free-text accessibility feature name, or None."""
    return _NAME_TO_CODE.get(_simplify(name or ""))


def venue_accessibility_codes(venue):
    """Fixed codes for the accessibility features recorded on a venue."""
    codes = []
    for name in venue.accessibility_features or []:
        code = accessibility_code_for(name)
        if code and code not in codes:
            codes.append(code)
    return codes


def venue_layout_codes(venue):
    """Fixed codes for the layouts a venue supports, each listed once."""
    codes = []
    for name in venue.supported_layouts or []:
        code = normalise_layout(name)
        if code and code not in codes:
            codes.append(code)
    return codes
