"""Utilities for dump file frontmatter parsing."""

import re
from typing import Tuple


def parse_frontmatter(path: str) -> Tuple[dict, str]:
    """
    Parse YAML frontmatter from a dump file.
    
    Args:
        path: Path to dump file with frontmatter
        
    Returns:
        Tuple of (frontmatter_dict, body_text)
    """
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Match YAML frontmatter pattern: ---\n...\n---\n
    pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(pattern, content, re.DOTALL)
    
    if not match:
        # No frontmatter, return empty dict and full content
        return {}, content
    
    frontmatter_text = match.group(1)
    body = match.group(2)
    
    # Parse simple YAML (key: value pairs)
    frontmatter = {}
    for line in frontmatter_text.split('\n'):
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            frontmatter[key.strip()] = value.strip()
    
    return frontmatter, body
