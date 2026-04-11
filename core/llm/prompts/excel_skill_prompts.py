"""
Prompt templates for the Excel Skill.
"""

from typing import List, Optional


def excel_plan_prompt(
    user_request: str,
    available_schema: Optional[str],
    available_documents: Optional[List[dict]],
    prior_sql_query: Optional[str] = None,
) -> str:
    """
    Build the prompt for generating an ExcelSkillPlan.

    The LLM receives the user's natural-language request along with
    available data sources (SQL schema and/or document table info)
    and must produce a structured plan for the Excel workbook.

    Args:
        prior_sql_query: A SQL query that was already executed in this
            conversation and produced the filtered result set the user
            is asking to export. When provided, the planner is instructed
            to use it as the primary source_query for the main data sheet
            (advisory — JOINs and column selection are allowed, but the
            WHERE clause must be preserved).
    """
    schema_section = ""
    if available_schema:
        schema_section = (
            "\n## Available Spreadsheet Data (SQL Queryable)\n"
            "The following tables are loaded in a SQLite database. "
            "You can reference these in `source_query` fields using standard SQL SELECT statements.\n"
            "**IMPORTANT**: Use the EXACT table and column names shown below (they include suffixes like _abc12).\n\n"
            f"```\n{available_schema}\n```\n"
        )

    docs_section = ""
    if available_documents:
        doc_lines = []
        for doc in available_documents:
            line = f"- **{doc['title']}** (ID: {doc['doc_id']}, type: {doc['type']})"
            if doc.get("tables"):
                line += f" — {doc['table_count']} table(s)"
            if doc.get("has_sql_data"):
                line += " [SQL available]"
            if doc.get("data_preview"):
                line += f"\n      {doc['data_preview']}"
            doc_lines.append(line)
        docs_section = (
            "\n## Available Documents\n"
            "These documents are uploaded in the thread. "
            "Tables extracted from PDFs/PPTX can be used as data sources.\n\n"
            + "\n".join(doc_lines)
            + "\n"
        )

    # Determine which data sources are actually available
    has_sql = bool(available_schema)
    has_docs = bool(available_documents and any(d.get("tables") for d in available_documents))

    source_guidance = ""
    if has_sql and not has_docs:
        source_guidance = (
            "\n**Data Source**: Only SQL-queryable spreadsheet data is available. "
            "Use `source_query` with SQL SELECT on all sheets. Do NOT use `extract:` columns.\n"
        )
    elif has_docs and not has_sql:
        source_guidance = (
            "\n**Data Source**: Only document-extracted tables are available (no SQL). "
            "Use `extract:<doc_id>` for column sources. Do NOT write SQL queries.\n"
        )
    elif has_sql and has_docs:
        source_guidance = (
            "\n**Data Source**: Both SQL spreadsheet data and document tables are available. "
            "Prefer SQL queries for spreadsheet data; use `extract:<doc_id>` for PDF/PPTX tables.\n"
        )
    else:
        source_guidance = (
            "\n**Data Source**: No structured data sources detected. "
            "Create the sheet structure based on the user's request with placeholder column names. "
            "Use `static:N/A` for column sources if no data is available.\n"
        )

    # Advisory section injected when a prior filtered SQL query exists
    prior_sql_section = ""
    if prior_sql_query:
        prior_sql_section = (
            "\n## Pre-filtered Data Source (IMPORTANT)\n"
            "A SQL query was already executed in this conversation and returned EXACTLY "
            "the filtered rows relevant to this Excel export:\n\n"
            f"```sql\n{prior_sql_query}\n```\n\n"
            "**Use this as the `source_query` for the primary data sheet.**\n"
            "- You MAY add column selection, JOINs, or ORDER BY to enrich the result.\n"
            "- You MUST preserve the WHERE clause — do not broaden or remove the filter.\n"
            "- Only ignore this hint if the user's request explicitly asks for a "
            "different or wider dataset.\n"
        )

    return (
        "You are an Excel workbook planner. Given a user's request and available data sources, "
        "create a detailed plan for an Excel (.xlsx) file.\n\n"
        "## Rules\n"
        "1. Each sheet must have a clear purpose and descriptive name (max 31 chars).\n"
        "2. For columns sourced from spreadsheet data, write a SQL SELECT query in `source_query`.\n"
        "   - Use standard SQLite syntax. Only SELECT queries are allowed.\n"
        "   - **CRITICAL**: Copy table names and column names EXACTLY from the schema — "
        "including any `_suffix` at the end. Do NOT shorten or modify them.\n"
        "   - Mark each column's `source` as `sql` when it comes from the query result.\n"
        "3. For computed columns, use `formula:<excel_formula>` with row-relative references "
        "(e.g., `formula:=C2*D2` will be applied to each row).\n"
        "4. **NLP COLUMNS (CRITICAL)**: When the user asks to classify, categorize, tag, "
        "extract intent, analyze sentiment, summarize, label, group by meaning, or add ANY "
        "column that does NOT already exist in the data schema — you MUST use `nlp:<instruction>`.\n"
        "   - `nlp:` columns are processed by a language model that reads each row and produces a value.\n"
        "   - The SQL `source_query` should fetch ONLY the raw data columns that exist in the table. "
        "NLP columns are added AFTER SQL extraction — do NOT include them in the SQL SELECT.\n"
        "   - **IMPORTANT**: The `nlp:` instruction MUST include the user's specific requirements "
        "verbatim — granularity expectations, examples, format, and constraints. "
        "Do NOT simplify or generalize the user's instructions.\n"
        "   - Examples:\n"
        "     - User asks 'categorize issues' → `nlp:classify into relevant categories`\n"
        "     - User asks 'extract sentiment' → `nlp:classify sentiment as positive/negative/neutral`\n"
        "     - User asks 'add granular subcategory, e.g. battery replacement request not just battery' "
        "→ `nlp:assign a specific, granular subcategory — e.g. \"battery replacement request\" not just \"battery\"`\n"
        "   - NEVER use `sql` as source for columns that require interpretation or don't exist in the schema.\n"
        "5. For constant values, use `static:<value>`.\n"
        "6. Use `group_by` and `aggregations` for pivot-table-style summaries "
        "(e.g., group_by=['region'], aggregations={'revenue': 'sum', 'orders': 'count'}).\n"
        "7. If the user asks for charts, specify them with proper column references.\n"
        "8. Keep the file name short, lowercase, with underscores (no spaces).\n"
        "9. When the user asks to 'export all data' or 'download the spreadsheet', "
        "create a single sheet with `SELECT * FROM <table>` as the source query.\n"
        "10. For document-extracted tables (PDFs/PPTX), use `source` as `extract:<doc_id>` on columns.\n"
        f"{prior_sql_section}"
        f"{source_guidance}"
        f"{schema_section}"
        f"{docs_section}"
        f"\n## User Request\n{user_request}\n\n"
        "Return ONLY a valid JSON object matching the required schema. "
        "No markdown fencing, no commentary, no text before or after the JSON.\n"
    )


def excel_nlp_column_prompt(
    column_instruction: str,
    input_data: List[str],
    column_name: str,
    prior_nlp_columns: Optional[List[str]] = None,
) -> str:
    """
    Build the prompt for NLP-based column interpretation.

    The LLM receives a batch of full row data and must return
    one interpreted value per input row.

    Args:
        prior_nlp_columns: Names of NLP columns already assigned to the data.
            When present, the prompt instructs the LLM to treat these as
            hierarchical context (e.g., Sub-Category should subdivide Category).
    """
    # Limit to prevent context overflow — process in batches externally
    data_str = "\n".join(f"{i+1}. {val}" for i, val in enumerate(input_data))

    # Build dependency-aware rule when prior NLP columns exist
    dependency_rule = ""
    if prior_nlp_columns:
        col_list = ", ".join(prior_nlp_columns)
        dependency_rule = (
            f"6. **DEPENDENCY**: The row data includes previously assigned NLP columns: [{col_list}]. "
            f"Your output for \"{column_name}\" MUST be consistent with and more specific than these prior assignments. "
            f"Treat them as a hierarchy — e.g., if a row has \"Category: Technical Issue\", "
            f"your Sub-Category should be a subdivision within \"Technical Issue\" "
            f"(like \"Battery Replacement\"), NOT an independent classification that duplicates the category.\n"
        )

    return (
        f"You are a data analyst. For each row below, analyze ALL the fields provided "
        f"and apply this instruction: **{column_instruction}**\n\n"
        f"Column to produce: {column_name}\n\n"
        f"## Input Data ({len(input_data)} rows)\n"
        "Each row shows all available fields in the format `Column: value | Column: value`.\n"
        "Use ALL fields to make your judgment — do not ignore numeric or categorical data.\n\n"
        f"{data_str}\n\n"
        "## Rules\n"
        f"1. Return exactly {len(input_data)} values in the `values` list, one per input row, in the same order.\n"
        "2. Each value should be a short string (1-3 words for classifications, a number for ratings, or a brief phrase).\n"
        "3. Be consistent — use the same label/rating for similar inputs.\n"
        "4. If a row is empty or has insufficient data, return 'N/A'.\n"
        "5. Base your judgment on the actual data in each row, not assumptions.\n"
        f"{dependency_rule}\n"
        "Return ONLY a valid JSON object matching the required schema. "
        "No markdown fencing, no commentary.\n"
    )


