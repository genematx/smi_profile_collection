"""Visual vocabulary for the guide, independent of terminal state and hardware."""

from .catalog import CATALOG
from .render import clean


COLORS = {
    "title": "ansibrightcyan bold",
    "heading": "ansicyan bold",
    "example": "ansibrightgreen",
    "breadcrumb": "ansicyan",
    "number": "bold",
    "topic": "ansibrightcyan",
    "device": "ansibrightblue",
    "part": "ansibrightblue",
    "parent": "ansiblue",
    "related": "ansibrightmagenta",
    "command": "ansibrightgreen",
    "navigation": "ansibrightblack",
    "help": "ansibrightyellow",
}

LABELS = {
    "topic": "topic", "device": "equipment", "part": "part", "parent": "parent",
    "related": "related", "command": "usage", "navigation": "navigation", "help": "help",
}


def role(match, context):
    if match.target.startswith(":"):
        return "help" if match.target == ":none" else "navigation"
    if match.target == "staff":
        return "help"
    relation = next((link.relation for link in CATALOG[context].links
                     if link.target == match.target), "")
    if relation == "child":
        return "part"
    if relation == "part of":
        return "parent"
    if relation in ("related", "uses"):
        return "related"
    kind = CATALOG[match.target].kind
    if kind in ("command", "workflow"):
        return "command"
    if kind in ("device", "component"):
        return "device"
    return "topic"


def menu_row(match, index, selected, context, *, color=True):
    """One numbered choice; selection is visible with or without color."""
    category = role(match, context)
    active = " reverse bold" if selected else ""
    number = f"{'>' if selected else ' '} {index + 1:>2}. "
    label = clean(match.label)
    if not color:
        label += " — " + LABELS[category]
    # Search scope is separate from relation: retain meaningful global context.
    if match.group == "Elsewhere in the guide":
        label += " · elsewhere"
    return [("class:number" + active, number), ("class:" + category + active, label), ("", "\n")]


def legend(color=True):
    if not color:
        return [("", "Numbers open entries; equipment / part / related / usage labels describe the links.")]
    fragments = []
    for category, label in (("topic", "Topics"), ("part", "Equipment / parts"),
                            ("parent", "Parent"), ("related", "Related"),
                            ("command", "Command / workflow help"), ("help", "Scientist help")):
        if fragments:
            fragments.append(("", " · "))
        fragments.append(("class:" + category, label))
    return fragments
