"""Keep glossary terms (brands, people, venues) out of translation.

Terms are replaced with placeholders before translating and restored after.

XTERM<n>X was picked by measuring survival through the en-id and en-ro models.
Brackets, underscores, angle tags and private use characters mostly did not
survive, while XTERM<n>X came through 81/81 times on both models. Models can
change the case of a placeholder or split it up, so restoring is tolerant.
"""
import re
from html import escape

MAX_TERMS = 1000

_PLACEHOLDER_RE = re.compile(r"(?<![A-Za-z0-9])X\s?TERM\s?(\d+)\s?X", re.IGNORECASE)
_TAG_RE = re.compile(r"(<[^>]*>)")


def load_file(path):
    """Read terms from a UTF-8 file: one per line, # starts a comment line."""
    with open(path, encoding="utf-8") as f:
        lines = [line.strip() for line in f]
    return [line for line in lines if line and not line.startswith("#")]


def merge_terms(*sources):
    """Return unique terms from strings or lists of strings, first spelling wins.

    Raises ValueError on anything else.
    """
    terms = {}
    for source in sources:
        if source is None:
            continue
        if isinstance(source, str):
            source = [source]
        if not isinstance(source, list):
            raise ValueError("glossary must be a list of strings")
        for term in source:
            if not isinstance(term, str):
                raise ValueError("glossary must be a list of strings")
            term = term.strip()
            if term:
                terms.setdefault(term.casefold(), term)
    if len(terms) > MAX_TERMS:
        raise ValueError(f"glossary exceeds {MAX_TERMS} terms")
    return list(terms.values())


def compile_terms(terms, text_format="text"):
    """Return a case-insensitive whole-word regex for terms, or None if empty."""
    if not terms:
        return None

    variants = set(terms)
    if text_format == "html":
        # AT&T is written as AT&amp;T in markup
        variants.update(escape(term, quote=False) for term in terms)

    # Longest first, so "Bali Hotel" wins over "Bali"
    alternatives = [
        r"\s+".join(re.escape(part) for part in variant.split())
        for variant in sorted(variants, key=len, reverse=True)
    ]
    return re.compile(r"(?<!\w)(?:" + "|".join(alternatives) + r")(?!\w)", re.IGNORECASE)


def protect(text, pattern, text_format="text"):
    """Replace terms with placeholders.

    Returns (masked text, {placeholder index: text as it was written}).
    """
    if pattern is None:
        return text, {}

    # Numbering starts past any placeholder lookalike already in the text,
    # which restore() then leaves alone.
    start = max((int(n) for n in _PLACEHOLDER_RE.findall(text)), default=-1) + 1
    indexes = {}

    def replace(match):
        surface = match.group(0)
        index = indexes.setdefault(surface, start + len(indexes))
        return f"XTERM{index}X"

    if text_format == "html":
        # Only text nodes: tags and attributes such as href stay untouched
        parts = _TAG_RE.split(text)
        parts[::2] = [pattern.sub(replace, part) for part in parts[::2]]
        masked = "".join(parts)
    else:
        masked = pattern.sub(replace, text)

    return masked, {index: surface for surface, index in indexes.items()}


def restore(text, mapping):
    """Put terms back. Returns (text, terms whose placeholder got lost)."""
    if not mapping:
        return text, []

    found = set()

    def replace(match):
        index = int(match.group(1))
        if index not in mapping:
            return match.group(0)
        found.add(index)
        return mapping[index]

    restored = _PLACEHOLDER_RE.sub(replace, text)
    return restored, [term for index, term in mapping.items() if index not in found]
