"""
Excel Skill — generates downloadable .xlsx workbooks from user requests.

Pipeline:
  1. LLM plans the workbook structure (sheets, columns, charts)
  2. Data is extracted deterministically (SQL queries, parsed doc tables)
  3. NLP columns are processed via LLM callback (sentiment, classification)
  4. Excel file is assembled deterministically via openpyxl
"""
