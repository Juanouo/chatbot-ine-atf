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

# --- Update filter functions ---
filters_dir = os.path.join(script_dir, 'filters')

with open('exports/filter-export.json', 'r') as f:
    filter_export = json.load(f)

filter_files = {
    'table_display_filter': os.path.join(filters_dir, 'table_display_filter.py'),
    'context_limit_filter': os.path.join(filters_dir, 'context_limit_filter.py'),
    'turn_logger_filter': os.path.join(filters_dir, 'turn_logger_filter.py'),
}

for func in filter_export:
    func_id = func.get('id')
    if func_id in filter_files:
        with open(filter_files[func_id], 'r') as f:
            func['content'] = f.read()
        func['updated_at'] = now
        print(f"Updated filter: {func['name']}")
        del filter_files[func_id]  # mark as handled

with open('exports/filter-export.json', 'w') as f:
    json.dump(filter_export, f, indent=2)

print("✅ exports/filter-export.json updated successfully!")
