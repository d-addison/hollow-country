"""Shared bytes for generated mission XML documents.

ElementTree's declaration option writes ``<?xml version='1.0'
encoding='utf-8'?>``. CF's XML reader refuses the single-quoted form (#168:
"No root tag economycore" for cfgeconomycore.xml on a friend server), so every
generator writes the double-quoted declaration vanilla missions use.
"""
import xml.etree.ElementTree as ET

DECLARATION = b'<?xml version="1.0" encoding="UTF-8"?>\n'


def document(root):
    """Return ``root`` as UTF-8 bytes behind the double-quoted declaration."""
    # encoding='utf-8' makes ElementTree omit its own declaration.
    return DECLARATION + ET.tostring(root, encoding='utf-8')
