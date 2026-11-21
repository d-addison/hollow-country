"""Shared bytes for generated mission XML documents.

ElementTree's declaration option writes ``<?xml version='1.0'
encoding='utf-8'?>``. CF's XML reader refuses the single-quoted form (#168:
"No root tag economycore" for cfgeconomycore.xml on a friend server), so every
generator writes the double-quoted declaration vanilla missions use.

CF_XML.Open reads a file line by line with native FGets. Build 150 crashed at
boot with an illegal write inside that loop (COT loot analysis reading an
optional-pack types.xml serialised as one 217,826-character line); build 149
read the same shape and logged a garbled-attribute parse error instead. A
1,299-character line in our own types.xml parses cleanly. The native line limit
is not measured, so generated documents keep every line at or under MAX_LINE.
"""
import copy
import xml.etree.ElementTree as ET

DECLARATION = b'<?xml version="1.0" encoding="UTF-8"?>\n'
MAX_LINE = 2048


def longest_line(data):
    """Return the byte length of the longest line in ``data``."""
    return max((len(line) for line in data.split(b'\n')), default=0)


def document(root):
    """Return ``root`` as UTF-8 bytes behind the double-quoted declaration.

    Output whose lines already fit MAX_LINE is unchanged. Otherwise an indented
    copy is serialised (``root`` is not modified); a line that still exceeds the
    bound raises instead of shipping a file FGets cannot read safely.
    """
    # encoding='utf-8' makes ElementTree omit its own declaration.
    data = DECLARATION + ET.tostring(root, encoding='utf-8')
    if longest_line(data) <= MAX_LINE:
        return data
    laid_out = copy.deepcopy(root)
    ET.indent(laid_out, space='    ')
    data = DECLARATION + ET.tostring(laid_out, encoding='utf-8')
    width = longest_line(data)
    if width > MAX_LINE:
        raise ValueError(f'generated XML line of {width} bytes exceeds {MAX_LINE} even when indented '
                         f'(root <{root.tag}>)')
    return data
