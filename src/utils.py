import re

def extract_columns(sql: str):
    # Normalize spacing
    sql_clean = " ".join(sql.replace("\n", " ").split())

    # Extract SELECT clause
    match = re.search(r"select (.*?) from", sql_clean, re.IGNORECASE)
    if not match:
        raise ValueError("Invalid SQL: no SELECT clause found")

    select_clause = match.group(1)

    # Split columns safely (no functions assumed)
    columns = [c.strip() for c in select_clause.split(",")]

    group_col = None
    value_col = None

    for col in columns:
        # Handle alias
        alias_match = re.match(r"(.*?)\s+as\s+(.*)", col, re.IGNORECASE)
        if alias_match:
            base = alias_match.group(1).strip()
            alias = alias_match.group(2).strip()
        else:
            base = col.strip()
            alias = None

        # Normalize base (remove table prefixes if any)
        base_name = base.split(".")[-1]

        if base_name == "valor_grupo":
            group_col = alias or base_name

        if base_name == "valor_indicador":
            value_col = alias or base_name

    return group_col, value_col