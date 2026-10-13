"""Deterministic catalog-only search and relationship navigation."""

from dataclasses import dataclass
import re

from .catalog import CATALOG


@dataclass(frozen=True)
class Match:
    target: str
    label: str
    group: str


def search(query, context="home", *, catalog=CATALOG):
    card = catalog[context]
    if not query.strip():
        return [Match(link.target, link.label, link.relation) for link in card.links]
    local = {link.target for link in card.links} | {context}
    terms = re.findall(r"[\w]+", query.casefold())
    if not terms:
        return []
    ranked = []
    for entry in catalog.cards.values():
        names = (entry.id, *entry.aliases)
        exact = query.strip() in names
        folded = query.strip().casefold() in [name.casefold() for name in names]
        labels = " ".join(link.label for link in card.links if link.target == entry.id)
        text = " ".join((*names, entry.title, entry.summary, *entry.keywords, labels)).casefold()
        if not exact and not all(term in text for term in terms):
            continue
        group = "In this context" if entry.id in local else "Elsewhere in the guide"
        # Exact identifiers always win; spelling similarity never resolves a card.
        phrase = query.strip().casefold()
        keyword_match = phrase in [word.casefold() for word in entry.keywords]
        rank = (not exact, not folded, entry.id not in local, not keyword_match,
                not entry.title.casefold().startswith(phrase), entry.title.casefold(), entry.id)
        ranked.append((rank, Match(entry.id, entry.title, group)))
    return [match for _, match in sorted(ranked)]


class Navigation:
    def __init__(self, start="home", *, catalog=CATALOG):
        catalog[start]  # validate before opening a prompt
        self.catalog = catalog
        self.history = [start]

    @property
    def current(self):
        return self.history[-1]

    def visit(self, target):
        self.catalog[target]
        if target != self.current:
            self.history.append(target)

    def back(self):
        if len(self.history) > 1:
            self.history.pop()

    def home(self):
        self.history[:] = ["home"]
