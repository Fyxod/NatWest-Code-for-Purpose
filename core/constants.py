from core.models.gpu_config import GPULLMConfig

# SETTINGS
SWITCHES = {
    "SUMMARIZATION": True,  # Summary is used by model to get a general idea of the document.
    "LOCAL_LLM": False,  # Local Ollama route
    "GEMINI": True,  # Enable Gemini route after LOCAL_LLM
    "OPENAI": False,  # Enable OpenAI route after LOCAL_LLM/GEMINI
    "DECOMPOSITION": True,  # Decomposition of query into sub-queries. This also serves as rewriting the query according to the context of the previous chat history.
    # This can be turned off if all the queries are independent and do not need context from previous chats.
    # please refer to core/Setup_Local_ollama.md for setting up local LLM server
    "GLM_OCR": True,  # GLM-OCR for structured document OCR (tables, formulas, figures). Runs alongside existing OCR.
    "EXCEL_SKILL": True,  # Excel creation/download skill — generates .xlsx from chat or sidebar
    "DOC_BATCH_REDUCER": True,  # MapReduce batching for multi-doc retrieval when token budget overflows
    "USE_VLM_FOR_ANSWER": False,  # Disabled: query-time page rendering depended on removed formats
    "DISABLE_THINKING": True,  # Disable LLM thinking mode (think=false) for faster inference
}

# GLM-OCR Configuration
GLM_OCR_MODEL = "glm-ocr-32k"  # Custom Modelfile: 32K context, 8K output (see core/parsers/Modelfile.glm-ocr)
GLM_OCR_WORKERS = 3  # Max concurrent GLM-OCR inferences (VRAM-aware)

CHUNK_COUNT = 12  # Number of chunks to retrieve from vector DB for each query

# Adaptive Retrieval Parameters
MAX_TOTAL_CHUNKS = 200  # Coverage over speed — MapReduce handles context overflow


EASYOCR_WORKERS = (
    1  # Number of parallel workers for EasyOCR (adjust based on your CPU/GPU power)
)
TESSERACT_WORKERS = (
    5 # Number of parallel workers for Tesseract OCR (adjust based on your CPU power)
)
EASYOCR_GPU = (
    False  # GPU mode: ~4-7x faster OCR, uses only ~200MB VRAM (negligible on 48GB)
)

PORT1 = 11434  # Ollama instance 1 — gpt-oss:20b (query answering)
PORT2 = 11435  # Ollama instance 2 — VLM (document processing, no queue contention with queries)

# Model context window (tokens). gpt-oss:20b full = 128K.
MODEL_CONTEXT_TOKENS = 128_000
MODEL_OUTPUT_RESERVE = 8_000  # Reserve for output generation

MAIN_MODEL = "gpt-oss:20b-50k-8k"

# LOCAL_LLM route model/port used by invoke_llm() (always local Ollama)
LOCAL_LLM_MODEL = MAIN_MODEL
LOCAL_LLM_PORT = PORT1

IMAGE_PARSER_LLM = "gemma3:12b"
VLM_MODEL = "qwen3.5:9b"  # Vision Language Model (retained for image-centric parsing)
# Provider models used by invoke_llm()
# Used if SWITCHES["GEMINI"] = True
GEMINI_MODEL = "gemini-2.5-flash"

# Used if SWITCHES["OPENAI"] = True
OPENAI_MODEL = "gpt-4o-mini"

# Graph constants used in agent
RETRIEVER = "retriever"
GENERATE = "generate"
WEB_SEARCH = "web_search"
ANSWER = "answer"
ROUTER = "router"
FAILURE = "failure"
GLOBAL_SUMMARIZER = "global_summarizer"
DOCUMENT_SUMMARIZER = "document_summarizer"
SELF_KNOWLEDGE = "self_knowledge"
SQL_QUERY = "sql_query"
EXCEL_CREATE = "excel_create"  # Excel skill: create downloadable .xlsx files
MAX_WEB_SEARCH = 2
MAX_SQL_RETRIES = 6
INTERNAL = "Internal"
EXTERNAL = "External"
