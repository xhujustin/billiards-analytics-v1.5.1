"""Lightweight text normalization and translation helpers for AI Coach."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


DEFAULT_TERMS: Dict[str, Dict[str, str]] = {
    "zh-TW": {
        "stance": "站姿",
        "bridge": "架桿",
        "follow_through": "送桿",
        "timing": "節奏",
        "stable": "穩定",
        "unstable": "不穩定",
    },
    "en": {
        "stance": "stance",
        "bridge": "bridge",
        "follow_through": "follow through",
        "timing": "timing",
        "stable": "stable",
        "unstable": "unstable",
    },
}


@dataclass
class TermTranslator:
    """Translate a small, well-defined coaching vocabulary."""

    locale: str = "zh-TW"
    glossary: Dict[str, Dict[str, str]] = field(
        default_factory=lambda: {key: value.copy() for key, value in DEFAULT_TERMS.items()}
    )

    def translate(self, key: str, locale: str | None = None, fallback: str | None = None) -> str:
        """Return the localized text for a glossary key."""

        target_locale = locale or self.locale
        if target_locale in self.glossary and key in self.glossary[target_locale]:
            return self.glossary[target_locale][key]

        if fallback is not None:
            return fallback

        return key

    def register(self, locale: str, key: str, value: str) -> None:
        """Register or override a translated term."""

        self.glossary.setdefault(locale, {})
        self.glossary[locale][key] = value


def normalize_locale(locale: str | None) -> str:
    """Normalize locale aliases used across simple tooling."""

    if not locale:
        return "zh-TW"

    normalized = locale.replace("_", "-").lower()
    aliases = {
        "zh": "zh-TW",
        "zh-tw": "zh-TW",
        "zh-hant": "zh-TW",
        "en": "en",
        "en-us": "en",
        "en-gb": "en",
    }
    return aliases.get(normalized, locale)
