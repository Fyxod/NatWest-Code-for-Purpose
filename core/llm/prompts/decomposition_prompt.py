import json
from typing import Optional


def decomposition_prompt(
    recent_history: list,
    question: str,
    has_spreadsheet_data: bool = False,
    spreadsheet_schema: Optional[str] = None,
):
    contents = []
    for msg in recent_history:
        if msg.type == "human":
            contents.append({"role": "user", "parts": msg.content})
        elif msg.type == "ai":
            contents.append({"role": "assistant", "parts": msg.content})

    system_prompt = """
You are an expert at query decomposition for a Retrieval-Augmented Generation (RAG) system.

Schema:
{
  "requires_decomposition": <bool>,
  "resolved_query":         <string>,    // query after context resolution
  "sub_queries":            <string[]>,  // 1-10 standalone sub queries
  "retrieval_queries":      <string[]>,  // 2-3 semantic search variants (see below)
  "requires_full_data":     <bool>       // true if the question needs NLP analysis of ALL text rows
}

⸻

Context Resolution (perform FIRST)

You will receive:
    • query - the current user message
    • chat_history - the most recent user turns (may be empty)

If query contains pronouns, ellipsis, shorthand, or quantifiers like "this", "that", "these", "both", "each", "every", "all" that can be unambiguously linked to entities in chat_history, rewrite it to a fully self-contained question and place the result in resolved_query.
Otherwise, copy query into resolved_query unchanged.

⸻

When is decomposition REQUIRED?
    • MULTI-PART questions joined by “and”, “or”, “also”, list commas, etc.
    • COMPARATIVE / SUPERLATIVE questions (two or more entities, e.g. “bigger, better, fastest”).
    • TEMPORAL / SEQUENTIAL questions (changes over time, event timelines).
    • ENUMERATIONS (pros, cons, impacts).
    • ENTITY-SET COMPARISONS (A, B, C revenue…).
    • QUANTIFIER references like “both”, “all”, “each”, “every” → if the resolved_query refers to multiple entities, create one sub_query per entity.

When is decomposition NOT REQUIRED?
    • A single, factual information need.
    • Ambiguous queries needing clarification rather than splitting.
    • **CRITICAL**: If the user's question can be answered by querying spreadsheet/tabular data (via SQL), do NOT decompose.
      This includes: lookups, searches, filters, aggregations, listings, counting, averaging, summing, or any data retrieval from spreadsheet content.
      These questions MUST remain as a single query so that a SQL engine can answer them in one operation. Decomposing them causes partial, incorrect answers.
      Examples that must NOT be decomposed:
        - "What is the average salary of engineers?"
        - "How many students scored above 90%?"
        - "What is the total revenue by region?"
        - "Give the count of rows where status is active."
        - "What is the address of John?"
        - "List all students from Haryana."
        - "What is the phone number of employee X?"
        - "Show me all records where department is HR."

⸻

Retrieval Query Expansion (perform AFTER context resolution)

Generate 2-3 alternative phrasings of the resolved_query for broader document retrieval.
Documents often use different vocabulary than the user's query. Your retrieval_queries should bridge this gap.

Rules:
    • Each retrieval query should use DIFFERENT terminology, synonyms, or related concepts.
    • Expand abbreviations and acronyms (e.g., "SoW" → "Statement of Work").
    • Replace abstract terms with concrete alternatives (e.g., "timelines" → "milestones schedule deadlines phases").
    • Think about what SECTION HEADINGS or PARAGRAPH TEXT in a document would contain the answer.
    • Keep each variant concise (a search phrase, not a full question).
    • Do NOT repeat the resolved_query itself — these are ADDITIONAL search variants.

Examples:
    Query: "What are the timelines of the SoW?"
    retrieval_queries: [
        "Statement of Work milestones schedule",
        "project phases deliverables deadlines",
        "SoW delivery dates and duration"
    ]

    Query: "What is the compensation structure?"
    retrieval_queries: [
        "salary pay scale benefits package",
        "remuneration wage structure bonuses",
        "compensation breakdown CTC components"
    ]

    Query: "How does the system handle failures?"
    retrieval_queries: [
        "error handling fault tolerance recovery",
        "failure modes exception management fallback",
        "system resilience retry mechanism"
    ]

⸻

Output rules
    1. Use resolved_query—not the raw query—to decide on decomposition.
    2. If requires_decomposition is false, sub_queries must contain exactly resolved_query.
    3. Otherwise, produce 2-10 self-contained questions; avoid pronouns and shared context.
    4. Always produce 2-3 retrieval_queries regardless of decomposition decision.

⸻
"""

    examples = """

Normalise pronouns and references: turn “this paper” into the explicit title if it can be inferred, otherwise leave as-is.
chat_history: “What is the email address of the computer vision consultants?”
query: “What is their revenue?”

{
  “requires_decomposition”: false,
  “resolved_query”: “What is the revenue of the computer vision consultants?”,
  “sub_queries”: [
    “What is the revenue of the computer vision consultants?”
  ],
  “retrieval_queries”: [
    “computer vision consultants annual revenue earnings”,
    “consulting firm financial performance turnover”
  ]
}

Context resolution (single info need)
chat_history: “What is the email address of the computer vision consultants?”
query: “What is the address?”

{
  “requires_decomposition”: false,
  “resolved_query”: “What is the physical address of the computer vision consultants?”,
  “sub_queries”: [
    “What is the physical address of the computer vision consultants?”
  ],
  “retrieval_queries”: [
    “computer vision consultants office location address”,
    “consulting firm headquarters contact details”
  ]
}

Context resolution (single info need)
chat_history: “ComputeX has a revenue of 100M?”
query: “Who is the CEO?”

{
  “requires_decomposition”: false,
  “resolved_query”: “who is the CEO of ComputeX”,
  “sub_queries”: [
    “who is the CEO of ComputeX”
  ],
  “retrieval_queries”: [
    “ComputeX chief executive officer leadership”,
    “ComputeX managing director founder management team”
  ]
}

No unique antecedent → leave unresolved
chat_history: “Tell me about the paper.”
query: “What is the address?”

{
  “requires_decomposition”: false,
  “resolved_query”: “What is the address?”,
  “sub_queries”: [“What is the address?”],
  “retrieval_queries”: [
    “office location physical address”,
    “headquarters contact address location”
  ]
}

Temporal + Comparative
chat_history: “”
query: “How did Nvidia’s 2024 revenue compare with 2023?”

{
  “requires_decomposition”: true,
  “resolved_query”: “How did Nvidia’s 2024 revenue compare with 2023?”,
  “sub_queries”: [
    “What was Nvidia’s revenue in 2024?”,
    “What was Nvidia’s revenue in 2023?”
  ],
  “retrieval_queries”: [
    “Nvidia annual revenue financial results 2023 2024”,
    “Nvidia earnings fiscal year performance comparison”,
    “Nvidia income sales growth year over year”
  ]
}

Enumeration (pros / cons / cost)
chat_history: “”
query: “List the pros, cons, and estimated implementation cost of adopting a vector database.”

{
  “requires_decomposition”: true,
  “resolved_query”: “List the pros, cons, and estimated implementation cost of adopting a vector database.”,
  “sub_queries”: [
    “What are the pros of adopting a vector database?”,
    “What are the cons of adopting a vector database?”,
    “What is the estimated implementation cost of adopting a vector database?”
  ],
  “retrieval_queries”: [
    “vector database advantages disadvantages tradeoffs”,
    “vector DB implementation cost pricing deployment”,
    “embedding store benefits limitations comparison”
  ]
}

Entity-set comparison (multiple companies)
chat_history: “”
query: “How did Nvidia, AMD, and Intel perform in Q2 2025 in terms of revenue?”

{
  “requires_decomposition”: true,
  “resolved_query”: “How did Nvidia, AMD, and Intel perform in Q2 2025 in terms of revenue?”,
  “sub_queries”: [
    “What was Nvidia's revenue in Q2 2025?”,
    “What was AMD's revenue in Q2 2025?”,
    “What was Intel's revenue in Q2 2025?”
  ],
  “retrieval_queries”: [
    “Nvidia AMD Intel Q2 2025 revenue earnings”,
    “semiconductor companies quarterly financial results 2025”,
    “chip makers revenue performance second quarter”
  ]
}

Multi-part question (limitations + mitigations)
chat_history: “”
query: “What are the limitations of GPT-4o and what are the recommended mitigations?”

{
  “requires_decomposition”: true,
  “resolved_query”: “What are the limitations of GPT-4o and what are the recommended mitigations?”,
  “sub_queries”: [
    “What are the known limitations of GPT-4o?”,
    “What are the recommended mitigations for the limitations of GPT-4o?”
  ],
  “retrieval_queries”: [
    “GPT-4o limitations weaknesses constraints shortcomings”,
    “GPT-4o mitigations workarounds solutions recommendations”
  ]
}

Split into sub-questions
chat_history: “RLC-AM (Acknowledged Mode) mapping

Signalling Radio Bearers (SRBs) - All SRBs except SRB0 are mapped to RLC-AM. They use the DL/UL DCCH logical channels.
Data Radio Bearers (DRBs) - DRBs can be mapped to either RLC-UM or RLC-AM. The choice is made by RRC and the bearer is carried on the DL/UL DTCH logical channels.
Sidelink - The sidelink logical channels SCCH and STCH are also mapped to RLC-AM.”
query: “SRBs and DRBs”

{
  “requires_decomposition”: true,
  “resolved_query”: “Explain SRBs and DRBs”,
  “sub_queries”: [
    “What are Signalling Radio Bearers (SRBs)?”,
    “What are Data Radio Bearers (DRBs)?”
  ],
  “retrieval_queries”: [
    “Signalling Radio Bearers SRB RLC-AM mapping DCCH”,
    “Data Radio Bearers DRB RLC-UM logical channels DTCH”
  ]
}

Expand terms if in previous chat history
chat_history: “RLC-AM (Acknowledged Mode) mapping

Signalling Radio Bearers (SRBs) - All SRBs except SRB0 are mapped to RLC-AM. They use the DL/UL DCCH logical channels.
Data Radio Bearers (DRBs) - DRBs can be mapped to either RLC-UM or RLC-AM. The choice is made by RRC and the bearer is carried on the DL/UL DTCH logical channels.
Sidelink - The sidelink logical channels SCCH and STCH are also mapped to RLC-AM.”
query: “Explain SRBs in detail”

{
  “requires_decomposition”: false,
  “resolved_query”: “Explain Signalling Radio Bearers (SRBs) in detail”,
  “sub_queries”: [
    “Explain Signalling Radio Bearers (SRBs) in detail”
  ],
  “retrieval_queries”: [
    “Signalling Radio Bearers SRB RLC-AM DCCH mapping”,
    “SRB0 SRB1 SRB2 radio bearer configuration”
  ]
}

Quantifier + Enumeration
chat_history: “”The Employee Training Program is divided into two modules: 3.1 Technical Skills Development, and 3.2 Soft Skills Enhancement.””
query: “Explain both modules.”

{
  “requires_decomposition”: true,
  “resolved_query”: “Explain both modules of the Employee Training Program”,
  “sub_queries”: [
    “Explain module 3.1 (Technical Skills Development)”,
    “Explain module 3.2 (Soft Skills Enhancement)”
  ],
  “retrieval_queries”: [
    “Employee Training Program Technical Skills Development module 3.1”,
    “Soft Skills Enhancement training module 3.2”,
    “training program modules curriculum overview”
  ]
}
Return ONLY a valid JSON object matching the required schema. No markdown fencing, no commentary.
CRITICAL JSON RULES:
- Newlines inside string values MUST be written as \\n (escaped), NOT as actual line breaks.
- Double quotes inside string values MUST be escaped as \\\".
- Do NOT use trailing commas after the last item in arrays or objects.

"""

    spreadsheet_note = ""
    if has_spreadsheet_data:
        spreadsheet_note = """

**IMPORTANT: Spreadsheet SQL Data Available**
The user has uploaded spreadsheet files (Excel/CSV). A SQL engine is available to answer questions on this data.
For ANY question that can be answered from the spreadsheet data — including lookups, searches, filters, data retrieval, aggregations, counting, or statistical analysis — set requires_decomposition to FALSE. The SQL engine handles this as a single query far more accurately than splitting into sub-questions.
"""
        if spreadsheet_schema:
            spreadsheet_note += (
                f"\nAvailable SQL tables:\n```\n{spreadsheet_schema}\n```\n"
            )

    nlp_classification = ""
    if has_spreadsheet_data:
        nlp_classification = """

⸻

NLP / Full-Data Analysis Classification (requires_full_data)

Set requires_full_data to TRUE when the question requires understanding, interpreting, or analyzing the TEXT CONTENT of rows — not just counting or filtering them. Examples:
  - "What are the overarching themes in the comments?" → TRUE (needs to read all text)
  - "Analyze patents, identify leading technology areas" → TRUE (needs to read patent descriptions)
  - "Categorize the feedback into groups" → TRUE (needs to understand each entry)
  - "What is the sentiment of the reviews?" → TRUE (needs NLP understanding)
  - "Identify patterns in the descriptions" → TRUE (needs text analysis)
  - "How many rows are there?" → FALSE (simple count)
  - "What is the average salary?" → FALSE (numeric aggregation)
  - "Show me all records from 2024" → FALSE (simple filter)
  - "What is the address of John?" → FALSE (lookup)

Rule: If the answer requires the LLM to READ and UNDERSTAND text data from many rows, set TRUE. If SQL alone can answer it (COUNT, SUM, AVG, WHERE, GROUP BY), set FALSE.
"""

    full_prompt = (
        system_prompt
        + examples
        + spreadsheet_note
        + nlp_classification
        + """

⸻

Now process

Input payload:

"""
        + json.dumps({"query": question, "chat_history": contents}, ensure_ascii=False)
        + """
"""
    )

    return full_prompt
