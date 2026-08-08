"""CSV and Excel extraction using pandas."""

from __future__ import annotations

import pandas as pd

from app.ingestion.extractors import ExtractedPage

# Cap rows to keep embedding/chunking bounded for very large sheets.
_MAX_ROWS = 50_000


def extract_csv(file_path: str) -> list[ExtractedPage]:
    """Extract text from CSV. Each file is one page."""
    try:
        df = pd.read_csv(file_path, nrows=_MAX_ROWS, encoding="utf-8", encoding_errors="replace")
    except Exception as exc:
        raise ValueError(f"Failed to read CSV file: {exc}") from exc
    return _dataframe_to_pages(df, source_type="csv")


def extract_excel(file_path: str) -> list[ExtractedPage]:
    """Extract text from Excel (.xlsx). Each sheet becomes a separate page."""
    try:
        sheets = pd.read_excel(file_path, sheet_name=None, engine="openpyxl")
    except Exception as exc:
        raise ValueError(
            "Failed to read Excel file. Only .xlsx (Office Open XML) is supported."
        ) from exc

    pages: list[ExtractedPage] = []
    for page_num, (sheet_name, df) in enumerate(sheets.items(), start=1):
        if len(df) > _MAX_ROWS:
            df = df.iloc[:_MAX_ROWS]
        text = f"Sheet: {sheet_name}\n\n{df.to_markdown(index=False)}"
        if text.strip():
            pages.append(ExtractedPage(
                text=text,
                page_number=page_num,
                metadata={
                    "source_type": "excel",
                    "sheet_name": str(sheet_name),
                    "rows": str(len(df)),
                    "columns": str(len(df.columns)),
                },
            ))
    return pages


def _dataframe_to_pages(df: pd.DataFrame, source_type: str) -> list[ExtractedPage]:
    text = df.to_markdown(index=False)
    if not text.strip():
        return []
    return [ExtractedPage(
        text=text,
        page_number=1,
        metadata={"source_type": source_type, "rows": str(len(df)), "columns": str(len(df.columns))},
    )]
