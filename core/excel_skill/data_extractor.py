"""
Data extraction for the Excel Skill.

Pulls tabular data from two sources:
  1. SQLiteManager — spreadsheet data already loaded into SQL tables
  2. Parsed document JSON — tables extracted from PDFs/PPTX during upload
"""

import json
import os
import re
from typing import Dict, List, Optional

import pandas as pd

from core.services.sqlite_manager import SQLiteManager


async def extract_from_spreadsheet(
    user_id: str,
    thread_id: str,
    sql_query: str,
) -> pd.DataFrame:
    """
    Execute a SQL query against the user's spreadsheet data and return a DataFrame.

    Uses SQLiteManager.execute_query() for security validation (SELECT-only,
    no dangerous keywords), then reads directly via pandas for a clean DataFrame.

    Returns:
        pandas DataFrame with the query results. Empty DataFrame on error.
    """
    # Validate via execute_query (checks SELECT-only, blocks dangerous keywords)
    # but don't use its markdown result — read directly with pandas instead
    validation = SQLiteManager.execute_query(user_id, thread_id, sql_query, max_rows=1)

    if not validation.get("success"):
        error = validation.get("error", "Unknown error")
        print(f"[ExcelSkill:data_extractor] SQL error: {error}")
        return pd.DataFrame()

    key = (user_id, thread_id)
    if key not in SQLiteManager._connections:
        return pd.DataFrame()

    conn = SQLiteManager._connections[key]
    try:
        df = pd.read_sql_query(sql_query, conn)
        return df
    except Exception as e:
        print(f"[ExcelSkill:data_extractor] DataFrame read error: {e}")
        return pd.DataFrame()


def extract_from_documents(
    user_id: str,
    thread_id: str,
    doc_ids: Optional[List[str]] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Extract tables from parsed document JSON files.

    Keys in the returned dict use the format "{doc_id}::{doc_title}" or
    "{doc_id}::{doc_title} (table N)" so callers can match by either doc_id or title.
    """
    parsed_dir = f"data/{user_id}/threads/{thread_id}/parsed"
    tables = {}

    if not os.path.exists(parsed_dir):
        return tables

    for filename in os.listdir(parsed_dir):
        if not filename.endswith(".json"):
            continue

        file_path = os.path.join(parsed_dir, filename)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        doc_id = data.get("id", "")
        if doc_ids and doc_id not in doc_ids:
            continue

        doc_title = data.get("title", filename.replace(".json", ""))
        full_text = data.get("full_text", "")

        # Extract tables from the text content
        extracted = _extract_all_tables(full_text)
        for i, df in enumerate(extracted):
            if len(extracted) == 1:
                key = f"{doc_id}::{doc_title}"
            else:
                key = f"{doc_id}::{doc_title} (table {i+1})"
            tables[key] = df

    if tables:
        total = sum(len(df) for df in tables.values())
        print(
            f"[ExcelSkill:data_extractor] Extracted {len(tables)} table(s), {total} total rows from documents"
        )
    else:
        print("[ExcelSkill:data_extractor] No tables found in any documents")

    return tables


def _extract_all_tables(text: str) -> List[pd.DataFrame]:
    """
    Extract all tables from text content using multiple strategies:
      1. Standard markdown pipe tables (| col | col |)
      2. [Table]...[/Table] wrapped tables (PPTX/PDF format)
      3. Space-pipe-space delimited tables (PPTX format without leading pipes)
    """
    tables = []

    # Strategy 1: Standard markdown pipe tables
    tables.extend(_extract_markdown_tables(text))

    # Strategy 2: [Table]...[/Table] wrapped content that isn't standard markdown
    tables.extend(_extract_tagged_tables(text))

    # Strategy 3: Space-delimited pipe tables (PPTX style: "Cell1 | Cell2 | Cell3")
    if not tables:
        tables.extend(_extract_loose_pipe_tables(text))

    return tables


def _extract_markdown_tables(text: str) -> List[pd.DataFrame]:
    """
    Extract standard markdown pipe tables from text content.

    Handles tables with format:
    | Header1 | Header2 |
    |---------|---------|
    | val1    | val2    |
    """
    tables = []
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Look for a line that starts with | and contains |
        if line.startswith("|") and line.count("|") >= 3:
            table_lines = [line]
            j = i + 1

            # Collect consecutive table lines
            while j < len(lines):
                next_line = lines[j].strip()
                if next_line.startswith("|") and "|" in next_line[1:]:
                    table_lines.append(next_line)
                    j += 1
                elif not next_line:
                    j += 1  # skip empty lines within table
                else:
                    break

            if (
                len(table_lines) >= 2
            ):  # header + at least 1 data row (separator optional)
                df = _parse_pipe_table(table_lines)
                if df is not None and not df.empty:
                    tables.append(df)

            i = j
        else:
            i += 1

    return tables


def _extract_tagged_tables(text: str) -> List[pd.DataFrame]:
    """
    Extract tables from [Table]...[/Table] blocks (used by PPTX/PDF parsers).

    Handles both:
      - Markdown-formatted content inside the tags (with leading |)
      - Space-pipe-space content (PPTX style: "Cell1 | Cell2 | Cell3")
    """
    tables = []
    pattern = re.compile(r"\[Table\](.*?)\[/Table\]", re.DOTALL | re.IGNORECASE)

    for match in pattern.finditer(text):
        block = match.group(1).strip()
        if not block:
            continue

        block_lines = [l.strip() for l in block.split("\n") if l.strip()]
        if not block_lines:
            continue

        # Check if lines start with | (standard markdown inside tags)
        if block_lines[0].startswith("|"):
            df = _parse_pipe_table(block_lines)
            if df is not None and not df.empty:
                tables.append(df)
        elif " | " in block_lines[0]:
            # PPTX-style: "Cell1 | Cell2 | Cell3" (no leading pipe)
            df = _parse_space_pipe_table(block_lines)
            if df is not None and not df.empty:
                tables.append(df)

    return tables


def _extract_loose_pipe_tables(text: str) -> List[pd.DataFrame]:
    """
    Extract tables that use space-pipe-space delimiters without leading pipes.

    PPTX tables are often formatted as:
      Header1 | Header2 | Header3
      Value1  | Value2  | Value3
    """
    tables = []
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Detect a line with multiple space-pipe-space delimiters (not a markdown table)
        if (
            " | " in line
            and not line.startswith("|")
            and not line.startswith("[")
            and line.count(" | ") >= 1
        ):
            table_lines = [line]
            j = i + 1

            while j < len(lines):
                next_line = lines[j].strip()
                if " | " in next_line and not next_line.startswith("["):
                    table_lines.append(next_line)
                    j += 1
                elif not next_line:
                    j += 1
                else:
                    break

            if len(table_lines) >= 2:  # header + at least 1 row
                df = _parse_space_pipe_table(table_lines)
                if df is not None and not df.empty:
                    tables.append(df)

            i = j
        else:
            i += 1

    return tables


def _parse_pipe_table(lines: List[str]) -> Optional[pd.DataFrame]:
    """Parse a standard markdown pipe table into a DataFrame."""
    try:
        # Parse header
        header_line = lines[0]
        headers = [cell.strip() for cell in header_line.strip("|").split("|")]
        headers = [h for h in headers if h]

        if not headers:
            return None

        # Skip separator line (---|----|----)
        data_start = 1
        if len(lines) > 1 and re.match(r"^\|[\s\-:|]+\|$", lines[1].strip()):
            data_start = 2

        # Parse data rows
        rows = []
        for line in lines[data_start:]:
            if re.match(r"^\|[\s\-:|]+\|$", line.strip()):
                continue  # skip separator lines
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            cells = cells[: len(headers)]  # trim to header count
            # Pad if needed
            while len(cells) < len(headers):
                cells.append("")
            rows.append(cells)

        if not rows:
            return None

        return pd.DataFrame(rows, columns=headers)

    except Exception as e:
        print(f"[ExcelSkill:data_extractor] Table parse error: {e}")
        return None


def _parse_space_pipe_table(lines: List[str]) -> Optional[pd.DataFrame]:
    """
    Parse a space-pipe-space delimited table into a DataFrame.

    Input format (no leading pipes):
      Header1 | Header2 | Header3
      Value1  | Value2  | Value3
    """
    try:
        # Parse header
        headers = [cell.strip() for cell in lines[0].split("|")]
        headers = [h for h in headers if h]

        if not headers:
            return None

        # Skip separator if present
        data_start = 1
        if len(lines) > 1 and re.match(
            r"^[\s\-:|]+$", lines[1].replace("|", "").strip()
        ):
            data_start = 2

        rows = []
        for line in lines[data_start:]:
            # Skip separator lines
            if re.match(r"^[\s\-:|]+$", line.replace("|", "").strip()):
                continue
            cells = [cell.strip() for cell in line.split("|")]
            cells = cells[: len(headers)]
            while len(cells) < len(headers):
                cells.append("")
            rows.append(cells)

        if not rows:
            return None

        return pd.DataFrame(rows, columns=headers)

    except Exception as e:
        print(f"[ExcelSkill:data_extractor] Space-pipe table parse error: {e}")
        return None


def get_document_info(
    user_id: str,
    thread_id: str,
    source_doc_ids: Optional[List[str]] = None,
) -> List[dict]:
    """
    Get metadata about available documents in the thread.

    Returns a list of dicts with title, doc_id, type, table count,
    and a preview of available data for use in the LLM planning prompt.
    """
    parsed_dir = f"data/{user_id}/threads/{thread_id}/parsed"
    docs = []

    if not os.path.exists(parsed_dir):
        return docs

    for filename in os.listdir(parsed_dir):
        if not filename.endswith(".json"):
            continue

        file_path = os.path.join(parsed_dir, filename)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        doc_id = data.get("id", "")
        if source_doc_ids and doc_id not in source_doc_ids:
            continue

        doc_type = data.get("type", "unknown")
        full_text = data.get("full_text", "")

        # Extract tables to get count and preview
        extracted_tables = _extract_all_tables(full_text)
        table_count = len(extracted_tables)

        # Build a data preview (first table's columns + first 3 rows)
        data_preview = ""
        if extracted_tables:
            preview_df = extracted_tables[0]
            cols = list(preview_df.columns)
            data_preview = f"Columns: {', '.join(cols)}"
            if len(preview_df) > 0:
                sample_rows = preview_df.head(3).to_dict(orient="records")
                data_preview += f"\n      Sample: {sample_rows}"

        docs.append(
            {
                "doc_id": doc_id,
                "title": data.get("title", filename.replace(".json", "")),
                "type": doc_type,
                "table_count": table_count,
                "tables": table_count > 0,
                "has_sql_data": data.get("has_sql_data", False),
                "data_preview": data_preview,
            }
        )

    return docs
