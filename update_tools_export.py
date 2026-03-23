#!/usr/bin/env python3
"""
Update postgres-tool-export.json and filter-export.json with current source file contents.
"""

import json
import os
import time

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

now = int(time.time())

# --- Update postgres tool ---
with open('postgres_llm_tool.py', 'r') as f:
    current_tool_content = f.read()

with open('exports/postgres-tool-export.json', 'r') as f:
    tools_export = json.load(f)

for tool in tools_export:
    if tool['id'] == 'postgres_database_tool':
        tool['content'] = current_tool_content
        tool['updated_at'] = now
        print(f"Updated tool: {tool['name']}")
        print(f"New timestamp: {tool['updated_at']}")
        break

with open('exports/postgres-tool-export.json', 'w') as f:
    json.dump(tools_export, f, indent=2)

print("✅ exports/postgres-tool-export.json updated successfully!")

# --- Update filter function ---
with open('table_display_filter.py', 'r') as f:
    current_filter_content = f.read()

with open('exports/filter-export.json', 'r') as f:
    filter_export = json.load(f)

for func in filter_export:
    if func['id'] == 'table_display_filter':
        func['content'] = current_filter_content
        func['updated_at'] = now
        print(f"Updated filter: {func['name']}")
        break

with open('exports/filter-export.json', 'w') as f:
    json.dump(filter_export, f, indent=2)

print("✅ exports/filter-export.json updated successfully!")
