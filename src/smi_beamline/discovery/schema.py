"""Immutable documentation records, not hardware or executable operations."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class Link:
    target: str
    label: str
    relation: str = "explore"


@dataclass(frozen=True)
class Card:
    id: str
    title: str
    summary: str
    kind: str = "topic"
    aliases: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    sections: tuple[tuple[str, str], ...] = ()
    links: tuple[Link, ...] = ()
    source: str = "docs/CONSOLE_DISCOVERY_PLAN.md"
    review: str = "staff preview"


class Catalog:
    """Validate references and exact identifiers without resolving Python paths."""

    def __init__(self, cards):
        entries, names = {}, {}
        for card in cards:
            if card.id in entries:
                raise ValueError(f"Duplicate card: {card.id}")
            if not card.title or not card.summary or not card.source:
                raise ValueError(f"Incomplete card: {card.id}")
            entries[card.id] = card
            for name in (card.id, *card.aliases):
                if name in names:
                    raise ValueError(f"Duplicate identifier: {name}")
                names[name] = card.id
        for card in entries.values():
            for link in card.links:
                if link.target not in entries:
                    raise ValueError(f"Broken link: {card.id} -> {link.target}")
        self.cards = MappingProxyType(entries)
        self.names = MappingProxyType(names)

    def resolve(self, name):
        """Exact, case-sensitive match only. Search handles suggestions separately."""
        return self.cards[self.names[name]]

    def __getitem__(self, identifier):
        return self.cards[identifier]
