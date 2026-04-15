import asyncio
from datetime import datetime, timezone
import json
import os
import time
import traceback
import uuid

import aiofiles
from langchain_core.messages import AIMessage, HumanMessage

from agent.graph_helpers import (
    build_grounded_inference_prompt,
    build_main_prompt,
    build_self_knowledge_prompt,
    parallel_search,
)
from agent.state import AgentState
from agent.tools.search import search_tavily as search_tool
from agent.tools.sql_query import execute_sql_query
from core.constants import *
from core.embeddings.context_enrichment import extract_query_entities
from core.embeddings.retriever import (
    expand_to_parent_chunks,
    get_thread_documents_retriever,
    rerank_chunks,
)
from core.services.triple_store import TripleStore
from core.llm.client import invoke_llm
from core.llm.output_schemas.main_outputs import CombinationLLMOutput
from core.llm.output_schemas.nlp_theme_output import NLPThemeExtraction
from core.utils.count_tokens import count_tokens
from core.llm.outputs import (
    MainLLMOutputExternal,
    MainLLMOutputInternal,
    MainLLMOutputInternalWithFailure,
    SelfKnowledgeLLMOutput,
)
from core.llm.prompts.combination_prompt import combination_prompt
from core.llm.prompts.doc_batch_prompt import doc_batch_prompt
from core.llm.prompts.grounded_inference_prompt import GROUNDED_INFERENCE_PREFIX
from core.llm.prompts.nlp_theme_prompt import nlp_theme_extraction_prompt
from core.llm.prompts.sql_batch_prompt import sql_batch_prompt

os.makedirs("DEBUG", exist_ok=True)


async def retriever(state: AgentState) -> AgentState:
    """
    Retrieves documents based on the user's question with balanced multi-document representation.

    This function now uses the robust retrieval strategy that ensures:
    1. Balanced representation across all documents in the thread
    2. Each document gets proportional chunks based on total document count
    3. Better coverage when multiple documents are present
    4. Re-ranking for optimal relevance and diversity
    """
    # Skip RAG retrieval when the thread contains only spreadsheet files.
    # Spreadsheet data is queried via SQL which is faster and more accurate
    # than text chunks extracted from spreadsheet cells.
    if state.has_spreadsheet_data and state.spreadsheet_only:
        print(
            f"[retriever] Skipping RAG — spreadsheet-only thread for user {state.user_id}"
        )
        state.chunks = []
        return state

    start_time = time.time()

    # Use the new robust retrieval function that ensures document diversity
    # Uses adaptive scaling based on document count
    query = state.query or state.resolved_query or state.original_query

    # Multi-query retrieval — collect distinct query variants
    # for broader coverage (original phrasing + resolved/rewritten versions)
    additional_queries = []
    if state.original_query and state.original_query != query:
        additional_queries.append(state.original_query)
    if (
        state.resolved_query
        and state.resolved_query != query
        and state.resolved_query not in additional_queries
    ):
        additional_queries.append(state.resolved_query)

    # Semantic expansion: LLM-generated alternative phrasings from decomposition
    if state.retrieval_queries:
        for rq in state.retrieval_queries:
            if rq and rq not in additional_queries and rq != query:
                additional_queries.append(rq)
        print(f"[Retrieval] +{len(state.retrieval_queries)} semantic expansion queries")

    retrieved_docs = await get_thread_documents_retriever(
        user_id=state.user_id,
        thread_id=state.thread_id,
        query=query,
        additional_queries=additional_queries if additional_queries else None,
        k=None,  # None enables adaptive scaling
        max_total_chunks=MAX_TOTAL_CHUNKS,
    )

    end_time = time.time()
    print(
        f"Retrieved {len(retrieved_docs)} documents in {end_time - start_time:.2f} seconds for user {state.user_id}"
    )

    # Re-rank chunks for better relevance and diversity
    rerank_start = time.time()
    reranked_docs = rerank_chunks(
        query=query,
        chunks=retrieved_docs,
        top_k=len(retrieved_docs),
        diversity_lambda=0.5,  # Balance between relevance and diversity
    )
    rerank_end = time.time()
    print(f"Re-ranking completed in {rerank_end - rerank_start:.2f} seconds")

    # Expand child chunks to parent-level context for richer LLM prompting.
    # Retrieval and reranking operate on small, precise child chunks; the LLM
    # receives the larger parent section for better answer grounding.
    expanded_docs = expand_to_parent_chunks(reranked_docs)
    print(
        f"Expanded {len(reranked_docs)} child chunks → {len(expanded_docs)} parent chunks"
    )

    modified_docs = []
    for doc in expanded_docs:
        metadata = doc.get("metadata", {}) or {}
        doc_title = metadata.get("title", "Unknown Title")
        doc_id = metadata.get("document_id", "")

        # Format content with document name prominently displayed
        content = doc.get("page_content", "")
        formatted_content = f"[Document: {doc_title}]\n\n{content}"

        modified_docs.append(
            {
                "document_id": doc_id,
                "title": doc_title,
                "page_no": metadata.get("page_no", 1),
                "file_name": metadata.get("file_name", ""),
                "content": formatted_content,
                "rerank_score": doc.get("rerank_score", 0.0),
            }
        )

    with open(f"DEBUG/retrieved_docs.json", "w") as f:
        json.dump(modified_docs, f, indent=2)

    state.chunks = modified_docs

    # Look up entity-relation triples for query entities
    try:
        query_entities = extract_query_entities(query)
        if query_entities:
            triple_ctx = await asyncio.to_thread(
                TripleStore.get_context_for_query,
                state.user_id,
                state.thread_id,
                query_entities,
            )
            if triple_ctx:
                state.triple_context = triple_ctx
                print(f"[Triples] Injected {len(triple_ctx.splitlines()) - 1} triples")
    except Exception as e:
        print(f"[Triples] Error querying triples: {e}")

    # Query-time visual page rendering was removed with PDF/PPT/DOC support.
    state.vlm_visual_answer = None

    # ── Filter low-relevance chunks (rerank_score < 0.5) ──
    # Chunks below 0.5 are essentially noise — the reranker considers them
    # irrelevant. Passing them to the LLM dilutes good context and can mislead.
    # Always keep at least the top 2 chunks as fallback.
    if state.chunks:
        MIN_RERANK_SCORE = 0.5
        filtered = [
            c for c in state.chunks if c.get("rerank_score", 0.0) >= MIN_RERANK_SCORE
        ]
        if len(filtered) < 2:
            # Keep top 2 by score as fallback even if below threshold
            filtered = sorted(
                state.chunks, key=lambda c: c.get("rerank_score", 0.0), reverse=True
            )[:2]
        dropped = len(state.chunks) - len(filtered)
        if dropped > 0:
            print(
                f"[ChunkFilter] Dropped {dropped} chunks with rerank_score < {MIN_RERANK_SCORE} "
                f"({len(filtered)} remaining)"
            )
        state.chunks = filtered

    # ── Lost in the Middle mitigation ──
    # Reorder so highest-scored chunks are at positions 0 and -1,
    # and lowest-scored chunks sit in the middle — combats positional
    # attention bias shown by transformer models on long contexts.
    if len(state.chunks) > 2:
        sorted_by_score = sorted(
            state.chunks, key=lambda c: c.get("rerank_score", 0.0), reverse=True
        )
        reordered: list = []
        # Place chunks at positions: even → front, odd → back
        # e.g. rank 0→pos 0, rank 1→pos -1, rank 2→pos 1, rank 3→pos -2, ...
        front: list = []
        back: list = []
        for i, chunk in enumerate(sorted_by_score):
            if i % 2 == 0:
                front.append(chunk)
            else:
                back.append(chunk)
        reordered = front + list(reversed(back))
        state.chunks = reordered
        print(
            f"[LostInMiddle] Reordered {len(state.chunks)} chunks (best at positions 0 and -1)"
        )

    # ── MapReduce: batch over document chunks if context budget overflows ──
    if SWITCHES.get("DOC_BATCH_REDUCER", False) and state.chunks:
        # Measure total token cost of all chunks
        all_chunk_text = "\n".join(c.get("content", "") for c in state.chunks)
        chunk_tokens = count_tokens(all_chunk_text, MAIN_MODEL)
        budget_tokens = _calculate_chunk_token_budget(state)

        if chunk_tokens > budget_tokens:
            print(
                f"[Doc Batch] Chunk tokens ({chunk_tokens}) exceed budget ({budget_tokens}) — "
                f"triggering MapReduce over {len(state.chunks)} chunks"
            )
            try:
                batched = await _batch_doc_answer(
                    chunks=state.chunks,
                    user_question=query,
                    budget_tokens=budget_tokens,
                )
                if batched:
                    state.doc_batched_answer = batched
                    print(
                        f"[Doc Batch] MapReduce complete — pre-analyzed answer stored"
                    )
            except Exception as e:
                print(
                    f"[Doc Batch] MapReduce failed: {e}, falling back to direct chunks"
                )

    return state


async def generate(state: AgentState) -> AgentState:
    prompt = build_main_prompt(state)

    async with aiofiles.open(f"DEBUG/main_prompt.json", "w") as f:
        await f.write(json.dumps(prompt, indent=2))

    # invoke_llm already handles retries (4 attempts) with self-correction
    # and fallback chains (GPU -> Gemini -> OpenAI).  This outer loop only
    # guards against unexpected transient errors (network, timeout).
    max_retries = 2
    for attempt in range(max_retries):
        try:
            start_time = time.time()
            if state.mode == EXTERNAL:
                response_schema = MainLLMOutputExternal
            else:
                if state.use_self_knowledge:
                    response_schema = MainLLMOutputInternalWithFailure
                else:
                    response_schema = MainLLMOutputInternal

            result = await invoke_llm(
                response_schema=response_schema,
                contents=prompt,
            )

            result = response_schema.model_validate(result)
            end_time = time.time()
            print("LLM result: ", result)
            print(f"LLM response time: {end_time - start_time:.2f} seconds")

            # Guard against blank/empty answers — retry if the model returned nothing
            answer_text = (result.answer or "").strip()
            if not answer_text and result.action in (ANSWER, None):
                print(
                    f"[generate] Blank answer detected (attempt {attempt+1}/{max_retries}), retrying..."
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                # Last attempt — fall through with a generic message
                result.answer = "I was unable to generate an answer for this query. Please try rephrasing your question."

            state.messages.append(HumanMessage(content=state.query))  # controversial
            state.messages.append(AIMessage(content=result.answer))
            state.messages.append(AIMessage("Action taken: " + result.action))

            # For actions that delegate to dedicated nodes (excel/chart create),
            # don't store the LLM's fabricated answer — the downstream node
            # will set the real answer after actual processing.
            if result.action in (EXCEL_CREATE, CHART_CREATE):
                state.answer = ""
            else:
                state.answer = result.answer
            state.action = result.action
            state.chunks_used = result.chunks_used or []
            state.web_search_queries = getattr(result, "web_search_queries", []) or []
            state.attempts += 1
            state.document_id = result.document_id or None
            state.sql_query = getattr(result, "sql_query", None)
            state.excel_request = getattr(result, "excel_request", None)
            state.chart_request = getattr(result, "chart_request", None)
            return state

        except Exception as e:
            print(f"Error in generate (attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                state.answer = "An error occurred while generating the answer. Please try again later."
                state.action = FAILURE
                return state
            await asyncio.sleep(1)  # brief pause before retry


async def web_search(state: AgentState) -> AgentState:
    queries = state.web_search_queries
    max_retries = 3
    for attempt in range(max_retries):
        try:
            results = await parallel_search(queries, search_tool)
            state.web_search = True
            # state.chunks = []
            state.messages.append(
                HumanMessage(content=f"Web search initiated for queries: {queries}")
            )
            state.web_search_attempts += 1
            state.web_search_results = results
            return state
        except Exception as e:
            print(f"Error in web search (attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                state.web_search = False
                state.web_search_results = []
                state.messages.append(
                    AIMessage(content="Web search failed. Please try again later.")
                )
                return state
            await asyncio.sleep(0.5)  # brief pause before retry


async def failure(state: AgentState) -> AgentState:
    """
    Handles the failure case when no action can be taken.
    """
    failure_message = (
        "I am unable to answer your question at this time. "
        "Please try rephrasing or asking a different question."
    )
    state.messages.append(AIMessage(content=failure_message))
    state.answer = failure_message
    return state
    # return END if the above line ever throws error


async def self_knowledge(state: AgentState) -> AgentState:
    # ── Grounded inference path ──
    # Triggered when: INTERNAL mode + self-knowledge off + chunks were retrieved.
    # The LLM couldn't answer verbatim from the chunks (action='failure'), but the
    # retrieved context is a valid foundation for analytical / inferential reasoning.
    if state.mode == INTERNAL and not state.use_self_knowledge and state.chunks:
        print(
            f"[grounded-inference] Falling back to grounded inference "
            f"({len(state.chunks)} chunks available)."
        )
        prompt = build_grounded_inference_prompt(state)
        try:
            with open("DEBUG/grounded_inference_prompt.json", "w") as f:
                json.dump(prompt, f, indent=2)
        except Exception:
            pass

        try:
            result = await invoke_llm(
                response_schema=SelfKnowledgeLLMOutput,
                contents=prompt,
            )
            result = SelfKnowledgeLLMOutput.model_validate(result)
            state.answer = GROUNDED_INFERENCE_PREFIX + result.answer
            state.messages.append(AIMessage(content=state.answer))
        except Exception as e:
            print(f"[grounded-inference] LLM call failed: {e}")
            state.answer = (
                "I was unable to generate an analytical response for this query. "
                "Please try rephrasing or asking a different question."
            )
        return state

    # ── External mode or self-knowledge explicitly off with no context ──
    # Return whatever the generate node already produced (usually a refusal).
    if state.mode == EXTERNAL or not state.use_self_knowledge:
        if not state.answer or not state.answer.strip():
            state.answer = (
                "I am unable to answer your question at this time. "
                "Please try rephrasing or asking a different question."
            )
        return state

    # ── Full self-knowledge path (use_self_knowledge=True, INTERNAL mode) ──
    print("Using self-knowledge to answer the question.")
    prompt = build_self_knowledge_prompt(state)
    with open(f"DEBUG/self_knowledge_prompt.json", "w") as f:
        json.dump(prompt, f, indent=2)

    result = await invoke_llm(
        response_schema=SelfKnowledgeLLMOutput,
        contents=prompt,
    )

    result = SelfKnowledgeLLMOutput.model_validate(result)
    state.messages.append(AIMessage(content=result.answer))
    state.answer = result.answer
    return state


async def document_summarizer(state: AgentState) -> AgentState:
    document_id = state.document_id
    if not document_id:
        print("No document ID provided for summarization.")
        state.summary = "No summary available for this document."
        return state

    print(f"Summarizing document with ID: {document_id}")

    state.messages.append(
        HumanMessage(content=f"Summarizing document with ID: {document_id}")
    )

    parsed_dir = f"data/{state.user_id}/threads/{state.thread_id}/parsed"
    os.makedirs(parsed_dir, exist_ok=True)

    for doc in state.chunks:
        # Support both flat chunk format (from retriever) and legacy metadata format
        meta = doc.get("metadata", {})
        doc_id = doc.get("document_id") or meta.get("document_id", "")
        if doc_id == document_id:
            file_name = doc.get("file_name") or meta.get("file_name", "")
            title = doc.get("title") or meta.get("title", "Unknown Title")
            if not file_name:
                print(f"Document {doc_id} has no file name, skipping...")
                continue

            name, _ = os.path.splitext(file_name)
            json_file_path = os.path.join(parsed_dir, f"{name}.json")

            if not os.path.exists(json_file_path):
                print(f"Parsed file {json_file_path} does not exist, skipping...")
                continue

            async with aiofiles.open(json_file_path, "r", encoding="utf-8") as f:
                content = await f.read()

            document_data = json.loads(content)
            if document_data.get("summary"):
                state.answer = f"Summary: \n {document_data['summary']}"
                state.summary = f"Summary for document {document_id}, title: {title}, summary: {document_data['summary']}"
                state.after_summary = ANSWER
                print(
                    f"Summary for document {document_id}, title: {title}, summary: {document_data['summary']}"
                )
            else:
                state.summary = "No summary available for this document. Use your own knowledge and context to provide an answer."
                state.after_summary = GENERATE
                print(f"No summary found for document {document_id}")
            break

    return state


async def global_summarizer(state: AgentState) -> AgentState:
    parsed_dir = f"data/{state.user_id}/threads/{state.thread_id}"
    os.makedirs(parsed_dir, exist_ok=True)
    json_file_path = os.path.join(parsed_dir, "global_summary.json")

    if not os.path.exists(json_file_path):
        print("Global summary for the documents not available")
        state.summary = "No global summary available for the documents. Use your own knowledge and context to provide an answer."
        state.after_summary = GENERATE
        return state

    async with aiofiles.open(json_file_path, "r", encoding="utf-8") as f:
        content = await f.read()

    global_summary_data = json.loads(content)
    if global_summary_data.get("summary"):
        state.answer = f"{global_summary_data['summary']}"
        state.summary = (
            f"Global summary of all the documents: {global_summary_data['summary']}"
        )
        state.after_summary = ANSWER
        print(f"Global summary: {global_summary_data['summary']}")
    else:
        state.summary = "No global summary available for the documents. Use your own knowledge and context to provide an answer."
        state.after_summary = GENERATE

    return state


# NLP query detection keywords — triggers chunked theme extraction on large results
_NLP_KEYWORDS = [
    "sentiment",
    "theme",
    "themes",
    "tone",
    "opinion",
    "opinions",
    "categorize",
    "categorise",
    "classify",
    "classification",
    "analyze comments",
    "analyse comments",
    "analyze feedback",
    "analyse feedback",
    "positive",
    "negative",
    "neutral",
    "overarching",
    "common patterns",
    "common themes",
    "recurring",
    "feedback analysis",
    "what do people say",
    "what are people saying",
    "mood",
    "attitude",
    "complaints",
    "praise",
    "criticism",
    "subjective",
    "qualitative analysis",
]


def _has_successful_sql_result(result: str | None) -> bool:
    """True only when the SQL tool returned a successful query payload."""
    return bool(result and result.startswith("**Query executed successfully.**"))


# Minimum row count to trigger NLP chunked extraction
_NLP_MIN_ROWS = 100
# Target rows per chunk — keeps each chunk within LLM context
_NLP_ROWS_PER_CHUNK = 200


def _is_nlp_query(question: str) -> bool:
    """Check if the user's question requires NLP/subjective analysis."""
    q_lower = question.lower()
    return any(kw in q_lower for kw in _NLP_KEYWORDS)


# Excel-intent keywords — when present, skip NLP theme extraction so the
# Excel skill handles per-row classification directly (avoids premature
# fabricated answers from the generate LLM).
_EXCEL_REQUEST_KEYWORDS = [
    "excel",
    "spreadsheet",
    "xlsx",
    "export to file",
    "download file",
    "create a file",
    "pivot table",
    "create an excel",
    "make an excel",
    "give me an excel",
]


def _is_excel_request(question: str) -> bool:
    """Check if the user explicitly wants an Excel/spreadsheet file."""
    q_lower = question.lower()
    return any(kw in q_lower for kw in _EXCEL_REQUEST_KEYWORDS)


def _parse_markdown_table_rows(result_text: str) -> tuple:
    """
    Parse a markdown table into header and data rows.
    Returns (header_line, separator_line, data_rows) or (None, None, []) if not a table.
    """
    lines = result_text.strip().split("\n")
    # Find the markdown table — look for header separator (|---|---|)
    header_line = None
    separator_line = None
    data_start = 0

    for i, line in enumerate(lines):
        if "|" in line and "---" in line:
            separator_line = line
            if i > 0:
                header_line = lines[i - 1]
            data_start = i + 1
            break

    if not separator_line:
        return None, None, []

    data_rows = [l for l in lines[data_start:] if l.strip() and "|" in l]
    return header_line, separator_line, data_rows


def _calculate_sql_token_budget(state: AgentState) -> int:
    """Calculate how many tokens are available for SQL result data.

    Builds the main prompt without SQL result, counts its tokens,
    and returns the remaining budget from the 128K context window.
    """
    # Temporarily clear SQL fields to measure prompt overhead
    saved_sql_result = state.sql_result
    saved_sql_nlp = state.sql_nlp_summary
    saved_sql_batched = state.sql_batched_answer
    state.sql_result = None
    state.sql_nlp_summary = None
    state.sql_batched_answer = None

    try:
        prompt_contents = build_main_prompt(state)
        prompt_text = "\n".join(
            msg["parts"] for msg in prompt_contents if isinstance(msg.get("parts"), str)
        )
        overhead_tokens = count_tokens(prompt_text, MAIN_MODEL)
    except Exception:
        # If prompt building fails, use a conservative estimate
        overhead_tokens = 15_000
    finally:
        state.sql_result = saved_sql_result
        state.sql_nlp_summary = saved_sql_nlp
        state.sql_batched_answer = saved_sql_batched

    safety_margin = 2000
    available = (
        MODEL_CONTEXT_TOKENS - MODEL_OUTPUT_RESERVE - safety_margin - overhead_tokens
    )
    return max(0, available)


async def _batch_sql_answer(
    result_text: str,
    user_question: str,
    budget_tokens: int,
) -> str | None:
    """
    MapReduce over SQL results that exceed context.
    Splits into batches, gets partial answers in parallel, combines them.
    """
    header_line, separator_line, data_rows = _parse_markdown_table_rows(result_text)
    if not data_rows:
        return None

    # Each batch gets: lightweight prompt (~1-2K tokens) + data chunk
    batch_prompt_overhead = 2000
    tokens_per_batch = budget_tokens - batch_prompt_overhead

    # Estimate average tokens per row from a sample
    sample_rows = data_rows[: min(20, len(data_rows))]
    sample_text = "\n".join(sample_rows)
    avg_tokens_per_row = max(
        1, count_tokens(sample_text, MAIN_MODEL) / len(sample_rows)
    )
    rows_per_batch = max(10, int(tokens_per_batch / avg_tokens_per_row))

    # Create batches
    batches = []
    for i in range(0, len(data_rows), rows_per_batch):
        batch_rows = data_rows[i : i + rows_per_batch]
        batch_table = "\n".join([header_line, separator_line] + batch_rows)
        batches.append(batch_table)

    total = len(batches)
    print(
        f"[SQL Batch] Splitting {len(data_rows)} rows into {total} batches "
        f"(~{rows_per_batch} rows each)"
    )

    # Map: process each batch in parallel
    async def process_batch(batch_data, batch_num):
        prompt = sql_batch_prompt(
            data=batch_data,
            user_question=user_question,
            batch_number=batch_num,
            total_batches=total,
        )
        try:
            result = await invoke_llm(
                response_schema=CombinationLLMOutput,
                contents=prompt,
                remove_thinking=True,
            )
            return result.answer
        except Exception as e:
            print(f"[SQL Batch] Batch {batch_num} failed: {e}")
            return None

    partial_answers = await asyncio.gather(
        *(process_batch(batch, i + 1) for i, batch in enumerate(batches))
    )

    valid_answers = [a for a in partial_answers if a]
    if not valid_answers:
        return None

    if len(valid_answers) == 1:
        return valid_answers[0]

    # Reduce: combine partial answers
    combo_prompt = combination_prompt(
        query=user_question,
        sub_answers=valid_answers,
    )
    try:
        combined = await invoke_llm(
            response_schema=CombinationLLMOutput,
            contents=combo_prompt,
            remove_thinking=True,
        )
        print(f"[SQL Batch] Combined {len(valid_answers)} partial answers")
        return combined.answer
    except Exception as e:
        print(f"[SQL Batch] Combination failed: {e}, returning concatenated")
        return "\n\n---\n\n".join(valid_answers)


def _calculate_chunk_token_budget(state: AgentState) -> int:
    """Calculate how many tokens are available for document chunk context.

    Builds the main prompt without chunks or doc_batched_answer, counts
    its tokens, and returns the remaining budget from the 128K context window.
    """
    # Temporarily clear chunk-related fields to measure prompt overhead
    saved_chunks = state.chunks
    saved_doc_batched = state.doc_batched_answer
    state.chunks = []
    state.doc_batched_answer = None

    try:
        prompt_contents = build_main_prompt(state)
        prompt_text = "\n".join(
            msg["parts"] for msg in prompt_contents if isinstance(msg.get("parts"), str)
        )
        overhead_tokens = count_tokens(prompt_text, MAIN_MODEL)
    except Exception:
        overhead_tokens = 15_000
    finally:
        state.chunks = saved_chunks
        state.doc_batched_answer = saved_doc_batched

    safety_margin = 2000
    available = (
        MODEL_CONTEXT_TOKENS - MODEL_OUTPUT_RESERVE - safety_margin - overhead_tokens
    )
    return max(0, available)


async def _batch_doc_answer(
    chunks: list,
    user_question: str,
    budget_tokens: int,
) -> str | None:
    """
    MapReduce over document chunks that exceed context budget.

    Groups chunks by document, sorts groups by best rerank score (descending),
    greedy bin-packs document groups into batches (each fits within budget_tokens),
    Maps in parallel (one LLM call per batch), filters [NO RELEVANT INFO] responses,
    and Reduces via combination_prompt.
    """
    if not chunks:
        return None

    # ── 1. Group chunks by document_id ──
    doc_groups: dict[str, list] = {}
    for chunk in chunks:
        doc_id = chunk.get("document_id", "unknown")
        doc_groups.setdefault(doc_id, []).append(chunk)

    # ── 2. Sort groups by best rerank_score descending ──
    def best_score(group):
        return max(c.get("rerank_score", 0.0) for c in group)

    sorted_groups = sorted(doc_groups.values(), key=best_score, reverse=True)

    # ── 3. Format a group into text and measure tokens ──
    MAP_PROMPT_OVERHEAD = 3000  # prompt template overhead per batch

    def format_group(group: list) -> str:
        parts = []
        for c in group:
            content = c.get("content", "").strip()
            parts.append(content)
        return "\n\n---\n\n".join(parts)

    # ── 4. Greedy bin-packing: fit as many document groups as possible per batch ──
    tokens_per_batch = budget_tokens - MAP_PROMPT_OVERHEAD
    batches: list[list[str]] = []  # each batch = list of group text strings
    current_batch: list[str] = []
    current_tokens = 0

    for group in sorted_groups:
        group_text = format_group(group)
        group_tokens = count_tokens(group_text, MAIN_MODEL)

        if current_batch and (current_tokens + group_tokens > tokens_per_batch):
            # Flush current batch, start a new one
            batches.append(current_batch)
            current_batch = [group_text]
            current_tokens = group_tokens
        else:
            current_batch.append(group_text)
            current_tokens += group_tokens

    if current_batch:
        batches.append(current_batch)

    total = len(batches)
    total_chunks = sum(len(g) for g in doc_groups.values())
    print(
        f"[Doc Batch] {total_chunks} chunks across {len(doc_groups)} docs → "
        f"{total} batch(es) (budget: {tokens_per_batch} tokens/batch)"
    )

    # ── 5. Map: process each batch in parallel ──
    async def process_batch(batch_texts: list[str], batch_num: int) -> str | None:
        combined_text = "\n\n===\n\n".join(batch_texts)
        prompt = doc_batch_prompt(
            chunks=combined_text,
            user_question=user_question,
            batch_number=batch_num,
            total_batches=total,
        )
        try:
            result = await invoke_llm(
                response_schema=CombinationLLMOutput,
                contents=prompt,
                remove_thinking=True,
            )
            answer = result.answer.strip()
            if "[NO RELEVANT INFO]" in answer.upper():
                return None
            return answer
        except Exception as e:
            print(f"[Doc Batch] Batch {batch_num} failed: {e}")
            return None

    partial_answers = await asyncio.gather(
        *(process_batch(batch, i + 1) for i, batch in enumerate(batches))
    )

    valid_answers = [a for a in partial_answers if a]
    if not valid_answers:
        return None

    if len(valid_answers) == 1:
        return valid_answers[0]

    # ── 6. Reduce: combine partial answers ──
    combo_prompt = combination_prompt(
        query=user_question,
        sub_answers=valid_answers,
    )
    try:
        combined = await invoke_llm(
            response_schema=CombinationLLMOutput,
            contents=combo_prompt,
            remove_thinking=True,
        )
        print(f"[Doc Batch] Combined {len(valid_answers)} partial answers")
        return combined.answer
    except Exception as e:
        print(f"[Doc Batch] Combination failed: {e}, returning concatenated")
        return "\n\n---\n\n".join(valid_answers)


async def _extract_nlp_themes(
    result_text: str,
    user_question: str,
    row_count: int,
) -> str | None:
    """
    Run chunked NLP theme extraction on a large SQL result.

    Splits the markdown table into chunks, runs lightweight theme
    extraction on each chunk in parallel, then merges results.

    Returns a formatted theme summary string, or None if extraction fails.
    """
    header_line, separator_line, data_rows = _parse_markdown_table_rows(result_text)
    if not data_rows or len(data_rows) < _NLP_MIN_ROWS:
        return None

    # Split data rows into chunks of ~_NLP_ROWS_PER_CHUNK rows each
    chunk_count = max(
        1, (len(data_rows) + _NLP_ROWS_PER_CHUNK - 1) // _NLP_ROWS_PER_CHUNK
    )
    chunk_size = max(1, len(data_rows) // chunk_count)
    chunks = []
    for i in range(0, len(data_rows), chunk_size):
        chunks.append(data_rows[i : i + chunk_size])

    # Last chunk absorbs any remainder from rounding
    if len(chunks) > chunk_count:
        chunks[chunk_count - 1].extend(row for c in chunks[chunk_count:] for row in c)
        chunks = chunks[:chunk_count]

    print(
        f"[NLP Theme Extraction] Detected NLP query, chunking {len(data_rows)} rows "
        f"into {len(chunks)} batches ({[len(c) for c in chunks]} rows each)"
    )

    # Extract text content from markdown table rows (take all cell values)
    def rows_to_text(rows):
        entries = []
        for row in rows:
            cells = [c.strip() for c in row.split("|") if c.strip()]
            entries.append(" | ".join(cells))
        return entries

    # Run theme extraction on each chunk in parallel
    async def extract_chunk(chunk_rows, batch_num):
        entries = rows_to_text(chunk_rows)
        prompt = nlp_theme_extraction_prompt(
            entries=entries,
            user_question=user_question,
            batch_number=batch_num,
            total_batches=len(chunks),
        )
        try:
            result = await invoke_llm(
                response_schema=NLPThemeExtraction,
                contents=prompt,
                remove_thinking=True,
            )
            return NLPThemeExtraction.model_validate(result)
        except Exception as e:
            print(f"[NLP Theme Extraction] Chunk {batch_num} failed: {e}")
            return None

    chunk_results = await asyncio.gather(
        *(extract_chunk(chunk, i + 1) for i, chunk in enumerate(chunks))
    )

    # Merge themes across chunks
    theme_map = {}  # theme_name_lower -> {theme, count, examples}
    total_analyzed = 0

    for cr in chunk_results:
        if cr is None:
            continue
        total_analyzed += cr.total_rows_analyzed
        for t in cr.themes:
            key = t.theme.strip().lower()
            if key in theme_map:
                theme_map[key]["count"] += t.count
                # Keep up to 3 unique examples
                existing = set(theme_map[key]["examples"])
                for ex in t.examples:
                    if len(theme_map[key]["examples"]) < 3 and ex not in existing:
                        theme_map[key]["examples"].append(ex)
            else:
                theme_map[key] = {
                    "theme": t.theme.strip(),
                    "count": t.count,
                    "examples": list(t.examples[:3]),
                }

    if not theme_map:
        return None

    # Sort by count descending
    sorted_themes = sorted(theme_map.values(), key=lambda x: x["count"], reverse=True)

    # Format as readable summary
    lines = [
        f"**Pre-Analyzed Themes** (from ALL {total_analyzed} rows across {len(chunks)} batches):\n"
    ]
    for i, t in enumerate(sorted_themes, 1):
        pct = (t["count"] / total_analyzed * 100) if total_analyzed > 0 else 0
        examples_str = "; ".join(f'"{ex}"' for ex in t["examples"])
        lines.append(
            f"{i}. **{t['theme']}** — {t['count']} entries ({pct:.0f}%)\n"
            f"   Examples: {examples_str}"
        )

    summary = "\n".join(lines)
    print(
        f"[NLP Theme Extraction] Extracted {len(sorted_themes)} themes from {total_analyzed} rows"
    )
    return summary


async def sql_query_node(state: AgentState) -> AgentState:
    """
    Executes a SQL query against the user's spreadsheet data in SQLite.
    The query is generated by the LLM in the generate step.
    After execution, the result is stored in state so the next generate
    call can use it to formulate the final answer.

    For NLP/subjective queries on large datasets, runs chunked theme
    extraction so the main LLM has accurate analysis from ALL rows.

    Uses dynamic token budget to fit as much data as possible in the
    128K context window. For results that exceed the budget, runs
    batched MapReduce processing (parallel partial answers + combination).
    """
    query = state.sql_query
    if not query:
        print("[sql_query_node] No SQL query provided")
        state.sql_result = "No SQL query was provided."
        state.sql_last_executed_query = None
        state.messages.append(
            AIMessage(content="SQL query action requested but no query was provided.")
        )
        return state

    print(f"[sql_query_node] Executing SQL: {query}")
    state.sql_last_executed_query = None
    state.sql_attempts += 1

    try:
        result = await execute_sql_query(
            user_id=state.user_id,
            thread_id=state.thread_id,
            query=query,
        )

        # NLP chunked theme extraction — needs ALL rows, not just the default 500.
        # LLM flag (requires_full_data) takes priority; keyword matching is fallback.
        user_q = state.original_query or state.query or ""
        is_nlp = state.requires_full_data or _is_nlp_query(user_q)

        # When the user explicitly wants Excel output, skip theme extraction —
        # the Excel skill will handle per-row NLP classification directly.
        # Theme extraction here would only cause the generate LLM to fabricate
        # a premature answer before the Excel file is created.
        if is_nlp and _is_excel_request(user_q):
            print(
                "[sql_query_node] NLP query but Excel output requested "
                "— skipping theme extraction (Excel skill will handle NLP)"
            )
            is_nlp = False

        if is_nlp:
            # Re-fetch with no row limit so NLP extraction sees the COMPLETE dataset
            full_result = await execute_sql_query(
                user_id=state.user_id,
                thread_id=state.thread_id,
                query=query,
                max_rows=None,
            )
            if not full_result.startswith("SQL query failed"):
                try:
                    nlp_summary = await _extract_nlp_themes(
                        result_text=full_result,
                        user_question=user_q,
                        row_count=full_result.count("\n"),
                    )
                    if nlp_summary:
                        state.sql_nlp_summary = nlp_summary
                        print(f"[NLP Theme Extraction] Complete — analyzed all rows")
                except Exception as e:
                    print(f"[NLP Theme Extraction] Failed: {e}")

        # ── Dynamic token budget: fit as much SQL data as possible ──
        # When NLP themes exist, keep a small sample (themes are the primary source).
        # Otherwise, dynamically calculate how much data fits in the 128K context.
        if state.sql_nlp_summary:
            max_chars = 4000  # ~50 rows — just enough for example references
            if len(result) > max_chars:
                row_count = result.count("\n")
                truncated = result[:max_chars]
                last_nl = truncated.rfind("\n")
                if last_nl > max_chars // 2:
                    truncated = truncated[:last_nl]
                result = (
                    f"{truncated}\n\n"
                    f"... [SAMPLE ONLY — {row_count} total rows in dataset] ...\n"
                    "Full-data theme analysis is provided above. "
                    "Use these rows only as example references."
                )
                print(
                    f"[sql_query_node] NLP mode — sample truncated to {len(result)} chars"
                )
        else:
            sql_tokens = count_tokens(result, MAIN_MODEL)
            budget_tokens = _calculate_sql_token_budget(state)
            print(f"[sql_query_node] SQL tokens: {sql_tokens}, budget: {budget_tokens}")

            if sql_tokens <= budget_tokens:
                # Single shot — full data fits in context
                print(f"[sql_query_node] Full result fits in context")
            else:
                # Result exceeds budget — re-fetch ALL rows for batched processing
                print(f"[sql_query_node] Result exceeds budget, batching...")
                full_result = await execute_sql_query(
                    user_id=state.user_id,
                    thread_id=state.thread_id,
                    query=query,
                    max_rows=None,
                )
                try:
                    batched_answer = await _batch_sql_answer(
                        result_text=full_result,
                        user_question=user_q,
                        budget_tokens=budget_tokens,
                    )
                except Exception as e:
                    print(f"[SQL Batch] Error: {e}")
                    batched_answer = None

                if batched_answer:
                    state.sql_batched_answer = batched_answer
                    # Truncate raw result to a sample for generate() context
                    max_sample_chars = min(budget_tokens * 3, len(result))
                    truncated = result[:max_sample_chars]
                    last_nl = truncated.rfind("\n")
                    if last_nl > max_sample_chars // 2:
                        truncated = truncated[:last_nl]
                    row_count = result.count("\n")
                    result = (
                        f"{truncated}\n\n"
                        f"... [SAMPLE — {row_count} total rows] ...\n"
                        "A comprehensive batched analysis of ALL rows is provided separately."
                    )
                    print(
                        f"[sql_query_node] Batched analysis complete, sample: {len(result)} chars"
                    )
                else:
                    # Batch failed — truncate to what fits
                    max_chars = budget_tokens * 3  # rough token→char conversion
                    truncated = result[:max_chars]
                    last_nl = truncated.rfind("\n")
                    if last_nl > max_chars // 2:
                        truncated = truncated[:last_nl]
                    result = (
                        f"{truncated}\n\n"
                        f"... [TRUNCATED — showing partial data] ...\n"
                        "Summarize, aggregate, or categorize the data in your answer."
                    )
                    print(
                        f"[sql_query_node] Batch failed, truncated to {len(result)} chars"
                    )

        state.sql_result = result
        if _has_successful_sql_result(result):
            state.sql_last_executed_query = query
        state.messages.append(HumanMessage(content=f"SQL query executed: {query}"))
        state.messages.append(AIMessage(content=f"SQL Result:\n{result}"))
        print(f"[sql_query_node] Query result length: {len(result)} chars")
    except Exception as e:
        error_msg = f"SQL execution error: {str(e)}"
        print(f"[sql_query_node] {error_msg}")
        state.sql_result = error_msg
        state.sql_last_executed_query = None
        state.messages.append(AIMessage(content=error_msg))

    return state


async def excel_skill_node(state: AgentState) -> AgentState:
    """
    Executes the Excel Skill: generates a downloadable .xlsx file
    based on the user's natural-language request.

    The pipeline uses LLM only for planning and NLP columns;
    data extraction and Excel assembly are deterministic.
    """
    from core.excel_skill.pipeline import generate_excel

    request_text = state.excel_request
    if not request_text:
        # Fallback: use the original query as the request
        request_text = state.query or state.original_query or "Export all data"

    # Enrich with user's original query so detailed instructions
    # (e.g., "granular subcategories like 'battery replacement request'")
    # reach the planner and NLP column prompts.
    original = state.original_query or state.query or ""
    if (
        original
        and request_text
        and original.strip().lower() != request_text.strip().lower()
    ):
        request_text = f"{original}\n\n(Excel specifics: {request_text})"

    print(f"[excel_skill_node] Generating Excel: {request_text}")

    try:
        result = await generate_excel(
            user_request=request_text,
            user_id=state.user_id,
            thread_id=state.thread_id,
            prior_sql_query=state.sql_last_executed_query or None,
        )

        state.excel_result = result.download_url

        # Build a user-friendly answer with download link
        if result.total_rows == 0:
            # Warn the user that no data was found
            state.answer = (
                f"I created the Excel file **{result.file_name}**, but it contains "
                f"**0 rows of data**. This usually means the SQL query didn't match "
                f"any rows in your spreadsheet, or the data source couldn't be read.\n\n"
                f"Please check that the correct file is uploaded and try rephrasing "
                f"your request.\n\n"
                f"[Download {result.file_name}]({result.download_url})"
            )
        else:
            download_info = (
                f"I've created your Excel file: **{result.file_name}**\n\n"
                f"{result.description}\n\n"
                f"- **Sheets:** {result.sheet_count}\n"
                f"- **Total rows:** {result.total_rows}\n\n"
                f"[Download {result.file_name}]({result.download_url})"
            )
            state.answer = download_info

        state.messages.append(
            AIMessage(content=f"Excel file created: {result.file_name}")
        )

        # Persist status metadata so chat-generated files appear in the list
        status_dir = f"data/{state.user_id}/threads/{state.thread_id}/excel_exports"
        os.makedirs(status_dir, exist_ok=True)
        _tracking_id = str(uuid.uuid4())
        status_data = {
            "file_name": result.file_name,
            "download_url": result.download_url,
            "description": result.description,
            "sheet_count": result.sheet_count,
            "total_rows": result.total_rows,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "request_text": request_text,
        }
        _status_path = os.path.join(status_dir, f"status_{_tracking_id}.json")
        with open(_status_path, "w", encoding="utf-8") as _f:
            json.dump(status_data, _f, ensure_ascii=False, indent=2)

        print(
            f"[excel_skill_node] Created {result.file_name} "
            f"({result.sheet_count} sheets, {result.total_rows} rows)"
        )

    except Exception as e:
        error_msg = f"Failed to create Excel file: {str(e)}"
        print(f"[excel_skill_node] {error_msg}")
        state.answer = (
            "I wasn't able to create the Excel file. "
            "Please try again or rephrase your request."
        )
        state.messages.append(AIMessage(content=error_msg))

    return state


async def chart_skill_node(state: AgentState) -> AgentState:
    """
    Executes the Chart Skill: generates a persisted interactive chart artifact
    that can be opened in chat or from the studio history.
    """
    from core.chart_skill.pipeline import generate_chart

    request_text = state.chart_request
    if not request_text:
        request_text = state.query or state.original_query or "Create a chart"

    original = state.original_query or state.query or ""
    if (
        original
        and request_text
        and original.strip().lower() != request_text.strip().lower()
    ):
        request_text = f"{original}\n\n(Chart specifics: {request_text})"

    print(f"[chart_skill_node] Generating chart: {request_text}")

    try:
        result = await generate_chart(
            user_request=request_text,
            user_id=state.user_id,
            thread_id=state.thread_id,
            prior_sql_query=state.sql_last_executed_query or None,
            allow_self_knowledge=bool(state.use_self_knowledge),
            allow_web_search=(state.mode == EXTERNAL),
        )

        state.chart_result = {
            "chart_id": result.chart_id,
            "title": result.title,
            "description": result.description,
            "chart_type": result.chart_type,
            "x_key": result.x_key,
            "y_keys": result.y_keys,
            "row_count": result.row_count,
            "item_url": result.item_url,
            "download_json_url": result.download_json_url,
            "download_csv_url": result.download_csv_url,
        }

        state.answer = (
            f"I've created an interactive chart: **{result.title}**\n\n"
            f"- **Type:** {result.chart_type}\n"
            f"- **Data points:** {result.row_count}\n"
            f"- **X-axis:** {result.x_key}\n"
            f"- **Series:** {', '.join(result.y_keys)}\n\n"
            "Use the chart button in this message to open and interact with it."
        )

        state.messages.append(
            AIMessage(content=f"Chart created: {result.title} ({result.chart_id})")
        )

        # Persist status metadata so chat-generated charts appear in studio history.
        status_dir = f"data/{state.user_id}/threads/{state.thread_id}/chart_exports"
        os.makedirs(status_dir, exist_ok=True)
        tracking_id = str(uuid.uuid4())
        status_data = {
            "chart_id": result.chart_id,
            "title": result.title,
            "description": result.description,
            "chart_type": result.chart_type,
            "x_key": result.x_key,
            "y_keys": result.y_keys,
            "row_count": result.row_count,
            "item_url": result.item_url,
            "download_json_url": result.download_json_url,
            "download_csv_url": result.download_csv_url,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "request_text": request_text,
        }
        status_path = os.path.join(status_dir, f"status_{tracking_id}.json")
        with open(status_path, "w", encoding="utf-8") as f:
            json.dump(status_data, f, ensure_ascii=False, indent=2)

        print(
            f"[chart_skill_node] Created chart {result.chart_id} "
            f"({result.chart_type}, {result.row_count} rows)"
        )

    except Exception as e:
        error_msg = f"Failed to create chart: {str(e)}"
        print(f"[chart_skill_node] {error_msg}")
        state.answer = (
            "I wasn't able to create the chart. "
            "Please try again or refine your chart request."
        )
        state.chart_result = None
        state.messages.append(AIMessage(content=error_msg))

    return state


def main_router(state: AgentState) -> str:
    if state.action == ANSWER:
        print("Router -> Answering the question")
        return ANSWER

    elif state.action == WEB_SEARCH:
        print("Router -> Initiating web search")
        if state.web_search_attempts < MAX_WEB_SEARCH:
            return WEB_SEARCH
        else:
            return FAILURE
    elif state.action == SQL_QUERY:
        # Break SQL loop: if the LLM re-issues the same query when a valid
        # result already exists, force it to answer.  But allow NEW/different
        # queries through (multi-part questions, drill-downs, corrections).
        if (
            _has_successful_sql_result(state.sql_result)
            and state.sql_last_executed_query
        ):
            new_q = (state.sql_query or "").strip().lower()
            prev_q = state.sql_last_executed_query.strip().lower()
            if new_q == prev_q or not new_q:
                print(
                    "Router -> Same SQL query repeated with valid result, forcing answer (loop breaker)"
                )
                return ANSWER
            print(
                f"Router -> Different SQL query (attempt {state.sql_attempts + 1}), allowing"
            )

        if state.sql_attempts < MAX_SQL_RETRIES:
            print(f"Router -> Executing SQL query (attempt {state.sql_attempts + 1})")
            return SQL_QUERY
        else:
            print("Router -> Max SQL retries reached, answering with what we have")
            return ANSWER

    elif state.action == EXCEL_CREATE:
        print("Router -> Creating Excel file")
        return EXCEL_CREATE

    elif state.action == CHART_CREATE:
        print("Router -> Creating chart artifact")
        return CHART_CREATE

    elif state.action == DOCUMENT_SUMMARIZER:
        print("Router -> Summarizing document")
        return DOCUMENT_SUMMARIZER

    elif state.action == GLOBAL_SUMMARIZER:
        print("Router -> Summarizing global context")
        return GLOBAL_SUMMARIZER

    elif state.action == FAILURE:
        return FAILURE

    return ANSWER


def summary_router(state: AgentState) -> str:
    if state.after_summary == ANSWER:
        print("Routing to answer after summarization")
        return ANSWER
    elif state.after_summary == GENERATE:
        print("Routing to generate after summarization")
        return GENERATE
    return ANSWER
