#!/usr/bin/env python3
"""Extract project name from pyproject.toml using pure Python parsing."""

import re
import sys
from pathlib import Path

def parse_toml(content):
    """
    Parse TOML content using a simple regex-based approach.
    This is a simplified parser that handles basic TOML structures.

    Args:
        content (str): TOML file content

    Returns:
        dict: Parsed TOML content as a nested dictionary
    """
    config = {}
    # Remove comments
    content = re.sub(r'#.*$', '', content, flags=re.MULTILINE)

    # Track current section
    current_section = config
    section_stack = [config]

    # Remove leading/trailing whitespace and split into lines
    lines = [line.strip() for line in content.split('\n') if line.strip()]

    for line in lines:
        # Section header
        section_match = re.match(r'\[([^\]]+)\]', line)
        if section_match:
            sections = section_match.group(1).split('.')
            current_section = config
            for section in sections:
                if section not in current_section:
                    current_section[section] = {}
                current_section = current_section[section]
            section_stack = [config]
            for s in sections[:-1]:
                section_stack.append(section_stack[-1][s])
            section_stack.append(current_section)
            continue

        # Key-value pair
        kv_match = re.match(r'^([^=]+)=\s*(.+)$', line)
        if kv_match:
            key = kv_match.group(1).strip()
            value = kv_match.group(2).strip()

            # Handle string values (remove quotes)
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]

            current_section[key] = value

    return config

def get_project_name(pyproject_path='pyproject.toml', default='myproject'):
    """
    Extract the project name from pyproject.toml using pure Python parsing.

    Args:
        pyproject_path (str): Path to pyproject.toml file
        default (str): Default project name if not found

    Returns:
        str: Project name
    """
    try:
        # Read the pyproject.toml file
        pyproject_content = Path(pyproject_path).read_text(encoding='utf-8')

        # Parse the TOML content
        config = parse_toml(pyproject_content)

        # Try to extract project name from different possible locations

        # 1. PEP 621 project metadata
        if 'project' in config and 'name' in config['project']:
            return config['project']['name']

        # 2. Poetry project configuration
        if 'tool' in config and 'poetry' in config['tool'] and 'name' in config['tool']['poetry']:
            return config['tool']['poetry']['name']

        # 3. Hatch project configuration
        if 'tool' in config and 'hatch' in config['tool'] and \
           'project' in config['tool']['hatch'] and \
           'name' in config['tool']['hatch']['project']:
            return config['tool']['hatch']['project']['name']

        # If no name found, return default
        return default

    except FileNotFoundError:
        print(f"Warning: {pyproject_path} not found.", file=sys.stderr)
        return default
    except Exception as e:
        print(f"Error parsing {pyproject_path}: {e}", file=sys.stderr)
        return default

if __name__ == '__main__':
    print(get_project_name())