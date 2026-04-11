import os
import re
import time
import traceback
import uuid
from pathlib import Path

import fitz
import pandas as pd

from app.socket_handler import sio
from core.constants import SWITCHES
from core.models.document import Document, Page
from core.parsers.excel_utils import (
    deduplicate_columns,
    detect_merged_header_rows,
    enrich_dataframe_with_metadata,
    find_header_row,
    flatten_multiindex_columns,
)
from core.parsers.extensions import IMAGE_EXTENSIONS, SUPPORTED_EXTENSIONS
from core.parsers.glm_ocr import glm_ocr_parse
from core.parsers.image import image_parser
from core.services.sqlite_manager import SQLiteManager


async def extract_document(
    path, title="Untitled", file_name=None, user_id=None, thread_id=None
):
    start_time = time.time()
    file_path = path
    ext = Path(path).suffix.lower()
    original_type = ext[1:]

    try:
        safe_file_name = file_name or os.path.basename(file_path)
    except Exception:
        traceback.print_exc()
        safe_file_name = os.path.basename(file_path)

    user_id = user_id or "unknown_user"
    thread_id = thread_id or "unknown_thread"
    doc_id = str(uuid.uuid4())

    async def safe_emit(channel: str, payload: dict):
        try:
            await sio.emit(channel, payload)
        except Exception as e:
            print(f"[emit-error] channel={channel} payload={payload} err={e}")

    if ext not in SUPPORTED_EXTENSIONS:
        print(f"Unsupported file type: {ext} for {safe_file_name}. Skipping.")
        await safe_emit(
            f"{user_id}/progress",
            {"message": f"Skipping {title}: unsupported file type {ext}"},
        )
        return None

    # --- Handle standalone images ---
    if ext in IMAGE_EXTENSIONS:
        try:
            await safe_emit(
                f"{user_id}/progress",
                {"message": f"{title} is an image, extracting text..."},
            )
            text = await image_parser(file_path)
        except Exception as e:
            print(f"Error processing image {safe_file_name}: {str(e)}")
            traceback.print_exc()
            return None

        # --- GLM-OCR Enhancement for standalone images (additive) ---
        if SWITCHES.get("GLM_OCR", False):
            try:
                print(f"[Image] Running GLM-OCR enhancement on {safe_file_name}...")
                glm_result = await glm_ocr_parse(file_path, mode="text")
                if glm_result and glm_result.strip():
                    text += f"\n\n{glm_result.strip()}"
                    print(
                        f"[Image] GLM-OCR enhancement added ({len(glm_result)} chars)"
                    )
            except Exception as e:
                print(f"[Image] GLM-OCR enhancement failed: {e}")
                traceback.print_exc()

        await safe_emit(
            f"{user_id}/progress",
            {"message": f"Processed {safe_file_name} successfully"},
        )

        return Document(
            id=doc_id,
            type=ext[1:],
            file_name=safe_file_name,
            content=[Page(number=1, text=text)],
            title=title,
            full_text=text,
        )

    if ext in {".xls", ".xlsx", ".csv"}:
        try:
            # Read Excel or CSV file into DataFrame(s)
            sheets_data = {}  # Tuples of (df, context_text)

            if ext == ".xlsx":
                # Use robust parsing for modern Excel
                xls = pd.ExcelFile(file_path, engine="openpyxl")
                for sheet_name in xls.sheet_names:
                    # 1. Detect Header & Context
                    header_idx, context = find_header_row(file_path, sheet_name)

                    # 2. Detect multi-level headers from merged cells
                    header_param = detect_merged_header_rows(
                        file_path, sheet_name, header_idx
                    )

                    # 3. Read DataFrame with correct header(s)
                    df = pd.read_excel(xls, sheet_name=sheet_name, header=header_param)

                    # 4. Flatten MultiIndex columns if multi-level headers detected
                    if isinstance(header_param, list):
                        df = flatten_multiindex_columns(df)

                    # 5. Enrich with Metadata (Colors, Comments)
                    # Note: We pass header_idx so we know where data starts
                    enrichment_header = (
                        header_param[-1]
                        if isinstance(header_param, list)
                        else header_param
                    )
                    df = enrich_dataframe_with_metadata(
                        df, file_path, sheet_name, enrichment_header
                    )

                    sheets_data[sheet_name] = (df, context)

            elif ext == ".xls":
                # Legacy Excel (less features supported, no openpyxl enrichment)
                xls = pd.ExcelFile(file_path, engine="xlrd")
                for sheet_name in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=sheet_name)
                    sheets_data[sheet_name] = (df, None)

            else:
                # CSV
                df = pd.read_csv(file_path)
                sheets_data["Sheet1"] = (df, None)

            # Load into SQLite for structured querying
            try:
                tables_info = SQLiteManager.load_spreadsheet(
                    user_id=user_id,
                    thread_id=thread_id,
                    doc_id=doc_id,
                    file_path=file_path,
                    file_name=safe_file_name,
                )
                if tables_info:
                    print(
                        f"[SQLite] Loaded {len(tables_info)} table(s) for {safe_file_name}: "
                        f"{list(tables_info.keys())}"
                    )
            except Exception as e:
                print(f"[SQLite] Failed to load {safe_file_name} into SQLite: {e}")
                traceback.print_exc()

            # --- Generate global workbook context ---
            # Create a summary of all sheets to give the LLM a "Table of Contents"
            workbook_summary_lines = ["# Workbook Structure Summary"]
            for s_name, (s_df, _) in sheets_data.items():
                col_list = ", ".join([str(c) for c in s_df.columns[:30]]) # Limit cols to avoid huge headers
                if len(s_df.columns) > 30:
                    col_list += ", ..."
                workbook_summary_lines.append(
                    f"- Sheet '{s_name}': {len(s_df)} rows. Columns: [{col_list}]"
                )
            workbook_summary = "\n".join(workbook_summary_lines) + "\n\n"

            # Also generate text representation for RAG/vector store
            text_parts = []
            pages = []
            page_num = 1

            for sheet_name, (df, context_text) in sheets_data.items():
                # Drop fully empty rows
                df = df.dropna(how="all")

                # --- Clean unicode whitespace (non-breaking spaces etc.) ---
                # Apply to ALL columns: replace \u00a0 and other unicode whitespace
                for col in df.columns:
                    if df[col].dtype == object or str(df[col].dtype) == "string":
                        df[col] = df[col].apply(
                            lambda x: (
                                re.sub(
                                    r"[\u00a0\u200b\u200c\u200d\ufeff\xa0]+",
                                    " ",
                                    str(x),
                                )
                                .replace("\n", " ")
                                .strip()
                                if isinstance(x, str) and str(x) != "nan"
                                else x
                            )
                        )

                # --- Fix "Unnamed" columns ---
                # Replace 'Unnamed: N' column headers with something more useful
                new_cols = []
                for i, col in enumerate(df.columns):
                    col_str = str(col)
                    # Clean non-breaking spaces from column names too
                    col_str = re.sub(r"[\u00a0\xa0]+", " ", col_str).strip()
                    if col_str.startswith("Unnamed"):
                        # Try to use the first non-null value in the column as a hint
                        first_val = df.iloc[:, i].dropna().head(1)
                        if not first_val.empty:
                            hint = str(first_val.iloc[0]).strip()
                            hint = re.sub(r"[\u00a0\xa0]+", " ", hint).strip()
                            # Only use as column name if it looks like a header (short text)
                            if (
                                hint
                                and len(hint) < 50
                                and not hint.replace(".", "").replace(",", "").isdigit()
                            ):
                                col_str = hint
                            else:
                                col_str = f"Column_{i}"
                        else:
                            col_str = f"Column_{i}"
                    new_cols.append(col_str)
                df.columns = new_cols

                # Deduplicate column names (handles duplicates after cleanup)
                df.columns = deduplicate_columns(list(df.columns))

                # Drop columns that are entirely NaN or empty
                df = df.dropna(axis=1, how="all")

                # Replace NaN with empty string for cleaner text output
                df = df.fillna("")

                # Remove rows where all values are empty strings
                df = df[
                    df.apply(lambda row: any(str(v).strip() != "" for v in row), axis=1)
                ]

                # Build a text summary: schema + data
                col_info = ", ".join([str(col) for col in df.columns])

                # Prepend the context (pre-header text) if it exists
                context_block = ""
                if context_text:
                    context_block = f"Context/Metadata:\n{context_text}\n"

                sheet_header = (
                    f"=== Spreadsheet: {safe_file_name} | Sheet: {sheet_name} ===\n"
                    f"{workbook_summary}"  # <- Global Context
                    f"{context_block}"  # <- Local Sheet Context
                    f"Columns: {col_info}\n"
                    f"Total rows: {len(df)}\n"
                )

                # Use markdown table for RAG - much more readable for the LLM
                try:
                    data_text = df.to_markdown(index=False)
                except Exception:
                    # Fallback: try to_string which is still more readable than JSON
                    try:
                        data_text = df.to_string(index=False)
                    except Exception:
                        data_text = str(df)

                # Final cleanup: remove any remaining \u00a0 from the output
                data_text = re.sub(r"[\u00a0\xa0]+", " ", data_text)

                sheet_text = sheet_header + "\nData:\n" + data_text
                # Collapse excessive whitespace but preserve single newlines for table rows
                sheet_text = re.sub(r"[^\S\n]{2,}", " ", sheet_text).strip()

                text_parts.append(sheet_text)
                pages.append(Page(number=page_num, text=sheet_text))
                page_num += 1

            full_text = "\n\n".join(text_parts)

            # Get the schema info to store with the document
            schema = SQLiteManager.get_schema(user_id, thread_id)

            await safe_emit(
                f"{user_id}/progress",
                {"message": f"Processed {safe_file_name} (Excel/CSV) successfully"},
            )

            return Document(
                id=doc_id,
                type="spreadsheet",
                file_name=safe_file_name,
                content=pages,
                title=title,
                full_text=full_text,
                has_sql_data=True,
                spreadsheet_schema=schema,
            )

        except Exception as e:
            print(f"Error processing Excel/CSV file {safe_file_name}: {str(e)}")
            traceback.print_exc()
            return None

    

    print(f"Parsing for file type {ext} is not implemented for {safe_file_name}.")
    await safe_emit(
        f"{user_id}/progress",
        {"message": f"Skipping {title}: parser for {ext} not implemented"},
    )
    return None