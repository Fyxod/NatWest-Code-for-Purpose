"""
Chart Skill pipeline — plan + extract + normalize + persist interactive chart data.
"""

import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd
from agent.tools.search import search_tavily

from core.chart_skill.planner import generate_chart_plan
from core.excel_skill.data_extractor import (
    extract_from_documents,
    extract_from_spreadsheet,
    get_document_info,
)
from core.llm.client import invoke_llm
from core.llm.output_schemas.chart_skill_outputs import ChartSkillWebData
from core.llm.prompts.chart_skill_prompts import chart_web_data_prompt
from core.services.sqlite_manager import SQLiteManager


@dataclass
class ChartSkillResult:
    chart_id: str
    title: str
    description: str
    chart_type: str
    x_key: str
    y_keys: List[str]
    row_count: int
    item_url: str
    download_json_url: str
    download_csv_url: str


def _sanitize_chart_type(chart_type: Optional[str]) -> str:
    value = (chart_type or "bar").strip().lower()
    if value in {"bar", "line", "area", "pie", "scatter", "radar", "composed"}:
        return value
    return "bar"


def _normalize_web_queries(
    user_request: str, queries: Optional[List[str]]
) -> List[str]:
    """Clean and deduplicate LLM-generated web search queries."""
    out: List[str] = []
    seen = set()

    for raw in queries or []:
        q = (raw or "").strip()
        if not q:
            continue
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
        if len(out) >= 4:
            break

    # Safe fallback when model asks for web but provides no usable query.
    if not out:
        out = [user_request.strip()]

    return out


async def _collect_chart_web_context(queries: List[str]) -> List[dict]:
    """Fetch optional web context for chart planning using model-generated queries."""
    contexts: List[dict] = []
    for query in queries:
        try:
            result = await search_tavily(query=query, max_results=5, depth="advanced")
            if result:
                contexts.append(result)
        except Exception as e:
            print(f"[ChartSkill] Web search failed for '{query}' (non-blocking): {e}")

    return contexts


def _extract_sql_table_names(sql_query: str) -> set[str]:
    """Extract table names referenced in FROM/JOIN clauses."""
    pattern = re.compile(r'\b(?:FROM|JOIN)\s+"?([A-Za-z0-9_]+)"?', re.IGNORECASE)
    return {match.group(1) for match in pattern.finditer(sql_query or "")}


def _resolve_allowed_tables(
    user_id: str,
    thread_id: str,
    source_doc_ids: Optional[List[str]],
) -> Optional[List[str]]:
    """Resolve allowed SQLite table names for an explicit source document selection."""
    if source_doc_ids is None:
        return None

    ordered: List[str] = []
    seen = set()
    for doc_id in source_doc_ids:
        for table_name in SQLiteManager.get_tables_for_document(
            user_id, thread_id, doc_id
        ):
            if table_name in seen:
                continue
            seen.add(table_name)
            ordered.append(table_name)
    return ordered


def _filter_schema_to_allowed_tables(
    schema: Optional[str],
    allowed_tables: Optional[List[str]],
) -> Optional[str]:
    """Filter schema text so planner sees only selected tables."""
    if not schema:
        return None
    if allowed_tables is None:
        return schema
    if not allowed_tables:
        return None

    allowed = set(allowed_tables)
    blocks = re.split(r'\n\n(?=Table:\s+")', schema.strip())
    kept: List[str] = []

    for block in blocks:
        match = re.search(r'Table:\s+"([^"]+)"', block)
        if match and match.group(1) in allowed:
            kept.append(block)

    return "\n\n".join(kept) if kept else None


def _ensure_sqlite_loaded(user_id: str, thread_id: str) -> None:
    """Ensure SQLite spreadsheet data is loaded (handles process restart cases)."""
    key = (user_id, thread_id)
    if key in SQLiteManager._connections and SQLiteManager.has_spreadsheet_data(
        user_id, thread_id
    ):
        return

    try:
        from core.database import db

        user = db.users.find_one({"threads." + thread_id: {"$exists": True}})
        if not user:
            return

        thread = user.get("threads", {}).get(thread_id)
        if not thread:
            return

        spreadsheet_files = []
        for doc in thread.get("documents", []):
            fname = doc.get("file_name", "").lower()
            if (
                fname.endswith(".xlsx")
                or fname.endswith(".xls")
                or fname.endswith(".csv")
            ):
                file_path = (
                    f"data/{user_id}/threads/{thread_id}/uploads/{doc['file_name']}"
                )
                if os.path.exists(file_path):
                    spreadsheet_files.append(
                        {
                            "path": file_path,
                            "file_name": doc["file_name"],
                            "doc_id": doc.get("docId"),
                        }
                    )

        if spreadsheet_files:
            SQLiteManager.reload_from_files(user_id, thread_id, spreadsheet_files)
    except Exception as e:
        print(f"[ChartSkill] SQLite reload error: {e}")


def _coerce_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Convert numeric-looking object columns (commas/currency/percent) to numeric."""
    out = df.copy()

    for col in out.columns:
        if pd.api.types.is_numeric_dtype(out[col]):
            continue

        series = out[col]
        if not (
            pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)
        ):
            continue

        cleaned = (
            series.astype(str)
            .str.replace(r"[,$%]", "", regex=True)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
            .replace({"": None, "None": None, "nan": None})
        )
        numeric = pd.to_numeric(cleaned, errors="coerce")

        non_null = cleaned.notna().sum()
        numeric_non_null = numeric.notna().sum()
        ratio = (numeric_non_null / non_null) if non_null > 0 else 0.0

        if ratio >= 0.7 and numeric_non_null > 0:
            out[col] = numeric

    return out


def _first_valid(items: List[str], valid_set: set[str]) -> Optional[str]:
    for item in items:
        if item in valid_set:
            return item
    return None


def _select_axes(
    df: pd.DataFrame,
    requested_x: Optional[str],
    requested_y: List[str],
) -> tuple[str, List[str]]:
    """Choose robust x/y axis columns from requested plan and actual dataframe."""
    columns = [str(c) for c in df.columns]
    col_set = set(columns)

    numeric_cols = [c for c in columns if pd.api.types.is_numeric_dtype(df[c])]
    non_numeric_cols = [c for c in columns if c not in numeric_cols]

    x_key = _first_valid([requested_x] if requested_x else [], col_set)
    if not x_key:
        x_key = (
            non_numeric_cols[0]
            if non_numeric_cols
            else (columns[0] if columns else "x")
        )

    requested_valid = [c for c in requested_y if c in col_set and c != x_key]
    requested_numeric = [c for c in requested_valid if c in numeric_cols]

    if requested_numeric:
        y_keys = requested_numeric
    else:
        y_keys = [c for c in numeric_cols if c != x_key]

    if not y_keys:
        fallback = [c for c in columns if c != x_key]
        y_keys = fallback[:1]

    return x_key, y_keys[:5]


def _serialize_value(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value
    return value


def _prepare_chart_rows(
    df: pd.DataFrame,
    chart_type: str,
    x_key: str,
    y_keys: List[str],
    limit: Optional[int],
) -> pd.DataFrame:
    """Shape dataframe for plotting: limit rows and apply chart-specific transforms."""
    used_cols = [x_key] + [y for y in y_keys if y != x_key]
    used_cols = [c for c in used_cols if c in df.columns]
    data = df[used_cols].copy()

    max_rows = limit or 300
    max_rows = max(20, min(500, int(max_rows)))

    if chart_type == "pie":
        y = y_keys[0]
        data = data[[x_key, y]].dropna(subset=[x_key, y])
        if not pd.api.types.is_numeric_dtype(data[y]):
            # pie needs numeric values; coerce then drop invalid
            data[y] = pd.to_numeric(data[y], errors="coerce")
            data = data.dropna(subset=[y])
        data = data.groupby(x_key, as_index=False)[y].sum()
        data = data.sort_values(y, ascending=False).head(min(max_rows, 30))
    elif chart_type == "scatter":
        # scatter works best with 1 y key
        if len(y_keys) > 1:
            y_keys[:] = y_keys[:1]
            data = data[[x_key, y_keys[0]]]
        data = data.dropna(subset=[x_key] + y_keys)
        data = data.head(max_rows)
    else:
        data = data.head(max_rows)

    return data


def _rows_to_records(df: pd.DataFrame) -> List[Dict[str, object]]:
    records: List[Dict[str, object]] = []
    for _, row in df.iterrows():
        obj: Dict[str, object] = {}
        for col in df.columns:
            obj[str(col)] = _serialize_value(row[col])
        records.append(obj)
    return records


async def _extract_chart_dataframe(
    user_id: str,
    thread_id: str,
    sql_query: Optional[str],
    source_doc_ids: Optional[List[str]] = None,
    allowed_tables: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Fetch chart source data from SQL first, then parsed document tables."""
    if sql_query:
        if allowed_tables is not None:
            referenced_tables = _extract_sql_table_names(sql_query)
            if referenced_tables and not referenced_tables.issubset(
                set(allowed_tables)
            ):
                print(
                    "[ChartSkill] Ignoring SQL query outside selected document tables"
                )
            else:
                df = await extract_from_spreadsheet(
                    user_id=user_id,
                    thread_id=thread_id,
                    sql_query=sql_query,
                )
                if not df.empty:
                    return df
        else:
            df = await extract_from_spreadsheet(
                user_id=user_id,
                thread_id=thread_id,
                sql_query=sql_query,
            )
            if not df.empty:
                return df

    doc_tables = extract_from_documents(user_id, thread_id, source_doc_ids)
    if doc_tables:
        # Use the largest extracted table for broadest coverage.
        _, df = max(doc_tables.items(), key=lambda item: len(item[1]))
        if not df.empty:
            return df

    # Last fallback: sample from a known table.
    if allowed_tables is not None:
        for table_name in allowed_tables:
            fallback_q = f'SELECT * FROM "{table_name}"'
            df = await extract_from_spreadsheet(
                user_id=user_id,
                thread_id=thread_id,
                sql_query=fallback_q,
            )
            if not df.empty:
                return df

        return pd.DataFrame()

    schema = SQLiteManager.get_schema(user_id, thread_id)
    if schema:
        match = re.search(r'Table:\s+"([^"]+)"', schema)
        if match:
            table_name = match.group(1)
            fallback_q = f'SELECT * FROM "{table_name}"'
            df = await extract_from_spreadsheet(
                user_id=user_id,
                thread_id=thread_id,
                sql_query=fallback_q,
            )
            if not df.empty:
                return df

    return pd.DataFrame()


async def _extract_chart_dataframe_from_web_context(
    user_request: str,
    plan_title: str,
    plan_description: str,
    chart_type: str,
    plan_x_key: Optional[str],
    plan_y_keys: List[str],
    web_context: Optional[List[dict]],
    allow_self_knowledge: bool,
) -> pd.DataFrame:
    """Build chart rows from web context (and optionally model self-knowledge)."""
    if not web_context and not allow_self_knowledge:
        return pd.DataFrame()

    prompt = chart_web_data_prompt(
        user_request=user_request,
        chart_title=plan_title,
        chart_description=plan_description,
        chart_type=chart_type,
        requested_x_key=plan_x_key,
        requested_y_keys=plan_y_keys,
        web_search_results=web_context,
        allow_self_knowledge=allow_self_knowledge,
    )

    rows_result = await invoke_llm(
        response_schema=ChartSkillWebData,
        contents=prompt,
    )
    rows_result = ChartSkillWebData.model_validate(rows_result)

    if not rows_result.rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows_result.rows)
    if df.empty:
        return pd.DataFrame()

    requested_x = rows_result.x_key or plan_x_key
    if requested_x and requested_x in df.columns:
        x_key = requested_x
    else:
        x_key = str(df.columns[0])

    requested_y = [
        col
        for col in (rows_result.y_keys or plan_y_keys)
        if col in df.columns and col != x_key
    ]
    if not requested_y:
        requested_y = [str(col) for col in df.columns if str(col) != x_key]

    if not requested_y:
        return pd.DataFrame()

    keep_cols = [x_key] + requested_y[:5]
    return df[keep_cols].copy()


async def generate_chart(
    user_request: str,
    user_id: str,
    thread_id: str,
    source_doc_ids: Optional[List[str]] = None,
    preferred_chart_type: Optional[str] = None,
    prior_sql_query: Optional[str] = None,
    allow_self_knowledge: bool = True,
    allow_web_search: bool = False,
) -> ChartSkillResult:
    """
    Generate a chart artifact and persist it for chat/studio history.

    The returned artifact is frontend-ready for Recharts.
    """
    explicit_no_local_docs = source_doc_ids is not None and len(source_doc_ids) == 0
    use_local_sources = not explicit_no_local_docs

    schema: Optional[str] = None
    doc_info: List[dict] = []
    allowed_tables: Optional[List[str]] = None

    if use_local_sources:
        _ensure_sqlite_loaded(user_id, thread_id)
        allowed_tables = _resolve_allowed_tables(user_id, thread_id, source_doc_ids)

        raw_schema = SQLiteManager.get_schema(user_id, thread_id)
        schema = _filter_schema_to_allowed_tables(raw_schema, allowed_tables)
        doc_info = get_document_info(user_id, thread_id, source_doc_ids)

    web_context: List[dict] = []
    plan = await generate_chart_plan(
        user_request=user_request,
        available_schema=schema,
        available_documents=doc_info if doc_info else None,
        preferred_chart_type=preferred_chart_type,
        prior_sql_query=prior_sql_query,
        web_search_results=None,
        allow_self_knowledge=allow_self_knowledge,
        allow_web_search=allow_web_search,
        web_context_already_fetched=False,
    )

    # Model-driven web search: if planner says context is insufficient, run its queries and re-plan.
    if allow_web_search and plan.needs_web_search:
        generated_queries = _normalize_web_queries(
            user_request, plan.web_search_queries
        )
        web_context = await _collect_chart_web_context(generated_queries)

        plan = await generate_chart_plan(
            user_request=user_request,
            available_schema=schema,
            available_documents=doc_info if doc_info else None,
            preferred_chart_type=preferred_chart_type,
            prior_sql_query=prior_sql_query,
            web_search_results=web_context,
            allow_self_knowledge=allow_self_knowledge,
            allow_web_search=allow_web_search,
            web_context_already_fetched=True,
        )

    chart_type = _sanitize_chart_type(preferred_chart_type or plan.chart_type)

    if use_local_sources:
        df = await _extract_chart_dataframe(
            user_id=user_id,
            thread_id=thread_id,
            sql_query=plan.sql_query,
            source_doc_ids=source_doc_ids,
            allowed_tables=allowed_tables,
        )
    else:
        df = await _extract_chart_dataframe_from_web_context(
            user_request=user_request,
            plan_title=plan.title,
            plan_description=plan.description,
            chart_type=chart_type,
            plan_x_key=plan.x_key,
            plan_y_keys=plan.y_keys,
            web_context=web_context,
            allow_self_knowledge=allow_self_knowledge,
        )

    if df.empty:
        if use_local_sources:
            raise ValueError(
                "No tabular data found for the selected source documents. "
                "Select different documents or refine your chart request."
            )
        raise ValueError(
            "Unable to derive reliable chart rows without source documents. "
            "Select source documents or provide explicit numeric values/range in your request."
        )

    df = _coerce_numeric_columns(df)
    x_key, y_keys = _select_axes(df, plan.x_key, plan.y_keys)

    if chart_type == "pie" and len(y_keys) > 1:
        y_keys = y_keys[:1]
    if chart_type == "scatter" and len(y_keys) > 1:
        y_keys = y_keys[:1]

    prepared_df = _prepare_chart_rows(df, chart_type, x_key, y_keys, plan.limit)
    if prepared_df.empty:
        raise ValueError(
            "Unable to prepare non-empty chart data from the selected columns."
        )

    chart_rows = _rows_to_records(prepared_df)

    chart_id = str(uuid.uuid4())
    export_dir = f"data/{user_id}/threads/{thread_id}/chart_exports"
    os.makedirs(export_dir, exist_ok=True)

    json_file_name = f"chart_{chart_id}.json"
    csv_file_name = f"chart_{chart_id}.csv"
    json_path = os.path.join(export_dir, json_file_name)
    csv_path = os.path.join(export_dir, csv_file_name)

    artifact = {
        "chart_id": chart_id,
        "title": plan.title,
        "description": plan.description,
        "chart_type": chart_type,
        "x_key": x_key,
        "y_keys": y_keys,
        "row_count": len(chart_rows),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "request_text": user_request,
        "sql_query": plan.sql_query,
        "data": chart_rows,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, ensure_ascii=False, indent=2)

    prepared_df.to_csv(csv_path, index=False)

    item_url = f"/chart-skill/item/{thread_id}/{chart_id}"
    download_json_url = f"/chart-skill/download/{thread_id}/{json_file_name}"
    download_csv_url = f"/chart-skill/download/{thread_id}/{csv_file_name}"

    return ChartSkillResult(
        chart_id=chart_id,
        title=plan.title,
        description=plan.description,
        chart_type=chart_type,
        x_key=x_key,
        y_keys=y_keys,
        row_count=len(chart_rows),
        item_url=item_url,
        download_json_url=download_json_url,
        download_csv_url=download_csv_url,
    )
