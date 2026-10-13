"""Plain, width-aware output shared by direct lookups and the browser."""

import textwrap

from .catalog import CATALOG


def clean(text):
    return "".join(char if char.isprintable() else " " for char in text)


def render_card(identifier, *, detail=False, width=88, catalog=CATALOG):
    card = catalog[identifier]
    lines = [f"{card.title}  [{card.kind}; {card.review}]", card.summary]
    for heading, text in card.sections:
        lines.extend(("", heading + ":"))
        lines.extend("  " + line for line in text.splitlines())
    if card.links:
        lines.extend(("", "Explore / related:"))
        for i, link in enumerate(card.links, 1):
            lines.append(f"  {i}. {link.label}  [{link.relation}]")
    lines.extend(("", f"Direct lookup: %guide show {card.id}"))
    if detail:
        lines.extend(("Aliases: " + (", ".join(card.aliases) or "none"), "Source: " + card.source))
    return "\n".join(
        textwrap.fill(clean(line), width=max(24, width), subsequent_indent="    ") if line else ""
        for line in lines
    )


def render_matches(matches, *, page=1, size=12):
    pages = max(1, (len(matches) + size - 1) // size)
    if not 1 <= page <= pages:
        raise ValueError(f"Page must be between 1 and {pages}.")
    if not matches:
        return "No documented matches. Try a broader term, or ask a beamline scientist."
    rows = [f"Matches — page {page}/{pages}"]
    for match in matches[(page - 1) * size:page * size]:
        rows.append(clean(f"  {match.label} [{match.group}]\n"))
        rows.append(f"    %guide show {match.target}")
    return "\n".join(rows)
