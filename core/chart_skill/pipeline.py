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


def _should_web_search_for_chart_request(user_request: str) -> bool:
    """Heuristic: trigger web search only for requests that imply external/current context."""
    text = (user_request or "").lower()
    if not text:
        return False

    web_intent_keywords = [
        "latest",
        "current",
        "market",
        "industry",
        "benchmark",
        "compare with",
        "vs global",
        "public data",
        "web",
        "internet",
        "news",
        "trend",
        "forecast",
    ]
    return any(keyword in text for keyword in web_intent_keywords)


async def _collect_chart_web_context(user_request: str) -> List[dict]:
    """Fetch optional web context for chart planning when external context is required."""
    try:
        result = await search_tavily(
            query=user_request, max_results=5, depth="advanced"
        )
        if not result:
            return []
        return [result]
    except Exception as e:
        print(f"[ChartSkill] Web search failed (non-blocking): {e}")
        return []


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
) -> pd.DataFrame:
    """Fetch chart source data from SQL first, then parsed document tables."""
    if sql_query:
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

    # Last fallback: if spreadsheet exists, sample from first table.
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
    _ensure_sqlite_loaded(user_id, thread_id)
    schema = SQLiteManager.get_schema(user_id, thread_id)
    doc_info = get_document_info(user_id, thread_id, source_doc_ids)
    web_context: List[dict] = []

    if allow_web_search and _should_web_search_for_chart_request(user_request):
        web_context = await _collect_chart_web_context(user_request)

    plan = await generate_chart_plan(
        user_request=user_request,
        available_schema=schema,
        available_documents=doc_info if doc_info else None,
        preferred_chart_type=preferred_chart_type,
        prior_sql_query=prior_sql_query,
        web_search_results=web_context,
        allow_self_knowledge=allow_self_knowledge,
        allow_web_search=allow_web_search,
    )

    chart_type = _sanitize_chart_type(preferred_chart_type or plan.chart_type)

    df = await _extract_chart_dataframe(
        user_id=user_id,
        thread_id=thread_id,
        sql_query=plan.sql_query,
        source_doc_ids=source_doc_ids,
    )

    if df.empty:
        raise ValueError(
            "No tabular data found to build a chart. Upload spreadsheet/tabular data and retry."
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
    download_json_url = f"/chart-skill/download/{thread_id}/{chart_id}.json"
    download_csv_url = f"/chart-skill/download/{thread_id}/{chart_id}.csv"

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
