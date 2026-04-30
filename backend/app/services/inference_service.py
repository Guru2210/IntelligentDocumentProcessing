"""
Inference Service — unified extraction pipeline.
Combines OCR + layout analysis + model inference.
"""
import json
import os
import tempfile
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

from app.config import settings
from app.services.ocr_service import run_ocr, OCRResult
from app.services.template_trainer import load_model_artifact, run_template_inference
from app.utils.export_utils import export_to_csv, export_to_excel, export_to_json


def run_extraction(
    file_bytes: bytes,
    filename: str,
    model_path: str,
    model_type: str,  # "template" or "neural"
    field_names: List[str],
    field_types: Optional[Dict[str, str]] = None,
    field_columns: Optional[Dict[str, List[str]]] = None,
    field_metadata: Optional[Dict[str, Any]] = None,
    output_format: str = "json",
    page_range: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full extraction pipeline:
    1. OCR
    2. (optional) filter page range
    3. Load model + run inference
    4. Build result JSON
    """
    # Step 1: OCR
    ocr_result: OCRResult = run_ocr(file_bytes, filename, dpi=settings.ocr_dpi)

    # Step 2: Filter page range
    pages = ocr_result.pages
    if page_range:
        pages = filter_page_range(pages, page_range)

    # Step 3: Inference
    if model_type == "template":
        model_artifact = load_model_artifact(model_path)
        extracted_fields = run_template_inference(model_artifact, pages)
    elif model_type == "neural":
        from app.services.neural_trainer import run_neural_inference
        neural_dir = os.path.join(model_path, "layoutlmv3-finetuned")
        extracted_fields = run_neural_inference(
            neural_dir, 
            pages, 
            field_names, 
            field_types=field_types or {},
            field_columns=field_columns or {},
            field_metadata=field_metadata or {},
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")



    # Step 4: Compute overall confidence
    field_confidences = [
        v.get("confidence", 0.0)
        for v in extracted_fields.values()
        if isinstance(v, dict)
    ]
    overall_confidence = float(round(
        sum(field_confidences) / len(field_confidences) if field_confidences else 0.0, 3
    ))

    # Build result JSON (Azure DI compatible format)
    result = {
        "status": "succeeded",
        "modelType": model_type,
        "confidence": overall_confidence,
        "pages": _build_page_results(pages),
        "tables": _extract_auto_tables(file_bytes, filename, pages),
        "fields": extracted_fields,
    }

    return result


def _build_page_results(pages: List[Dict]) -> List[Dict]:
    return [
        {
            "pageNumber": p["page_number"],
            "width": p["width"],
            "height": p["height"],
            "wordCount": len(p.get("words", [])),
            "lines": p.get("lines", []),
            "words": [
                {
                    "text": w["text"],
                    "boundingBox": [w["x0"], w["y0"], w["x1"], w["y1"]],
                    "confidence": w.get("confidence", 1.0),
                }
                for w in p.get("words", [])
            ],
        }
        for p in pages
    ]


def _extract_table_fields_from_pdf(
    file_bytes: bytes,
    pages: List[Dict],
    field_types: Dict[str, str],
    field_columns: Dict[str, List[str]],
) -> Dict[str, Any]:
    """
    For each table field with defined columns, use pdfplumber to extract the
    raw grid and map it to the user-defined column names via fuzzy header matching.
    Returns {field_name: {type: array, valueArray: [...]}}
    """
    table_fields = {fn: cols for fn, cols in field_columns.items()
                    if field_types.get(fn) == "table" and cols}
    if not table_fields:
        return {}

    results: Dict[str, Any] = {}
    try:
        import pdfplumber
        import io
        allowed_pages = {p["page_number"] for p in pages}

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            all_raw_tables: List[Dict] = []
            for page_idx, page in enumerate(pdf.pages):
                page_num = page_idx + 1
                if allowed_pages and page_num not in allowed_pages:
                    continue
                for raw_table in (page.extract_tables() or []):
                    if raw_table:
                        all_raw_tables.append({"page": page_num, "rows": raw_table})

        for field_name, col_names in table_fields.items():
            col_names_clean = [c.strip().lower() for c in col_names]
            field_rows: List[Dict] = []

            for raw in all_raw_tables:
                raw_rows = raw["rows"]
                page_num = raw["page"]
                if not raw_rows:
                    continue

                # Try to find a header row matching at least half the column names
                header_idx = None
                col_mapping: Dict[int, str] = {}

                for r_idx, row in enumerate(raw_rows[:5]):
                    matches: Dict[int, str] = {}
                    for c_idx, cell in enumerate(row or []):
                        cell_clean = str(cell or "").strip().lower()
                        if not cell_clean:
                            continue
                        for user_col, user_col_clean in zip(col_names, col_names_clean):
                            if (cell_clean in user_col_clean or user_col_clean in cell_clean
                                    or _col_similarity(cell_clean, user_col_clean) > 0.5):
                                matches[c_idx] = user_col
                                break
                    if len(matches) >= max(1, len(col_names) // 2):
                        header_idx = r_idx
                        col_mapping = matches
                        break

                # Fallback: assign columns positionally
                if header_idx is None:
                    col_mapping = {i: col_names[i] for i in range(min(len(col_names), len(raw_rows[0] or [])))}
                    data_start = 0
                else:
                    data_start = header_idx + 1

                if not col_mapping:
                    continue

                for row in raw_rows[data_start:]:
                    obj: Dict[str, Any] = {}
                    has_content = False
                    for c_idx, user_col in col_mapping.items():
                        cell_text = str(row[c_idx] if c_idx < len(row or []) else "").strip()
                        if cell_text:
                            has_content = True
                        obj[user_col] = {
                            "type": "string",
                            "valueString": cell_text,
                            "confidence": 0.95,
                        }
                    if has_content:
                        field_rows.append({"type": "object", "valueObject": obj})

            if field_rows:
                results[field_name] = {
                    "type": "array",
                    "valueArray": field_rows,
                    "confidence": 0.95,
                }

    except Exception as e:
        print(f"[Inference] Hybrid table extraction failed: {e}")

    return results


def _col_similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity between two strings."""
    if not a or not b:
        return 0.0
    set_a, set_b = set(a.split()), set(b.split())
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / max(len(set_a), len(set_b))


def _extract_auto_tables(file_bytes: bytes, filename: str, pages: List[Dict]) -> List[Dict]:
    """Auto-detected tables using native pdf grid logic via pdfplumber."""
    if not filename.lower().endswith(".pdf"):
        return []

    tables_out = []
    try:
        import pdfplumber
        import io
        
        # Determine allowed pages if filtered
        allowed_pages = {p["page_number"] for p in pages}

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                page_num = page_idx + 1
                if allowed_pages and page_num not in allowed_pages:
                    continue
                
                # Extract all tables on the page
                page_tables = page.extract_tables()
                for table in page_tables:
                    if not table:
                        continue
                    
                    # Convert to Azure structure
                    cells = []
                    row_count = len(table)
                    col_count = max((len(r) for r in table if r), default=0)
                    
                    for r_idx, row in enumerate(table):
                        for c_idx, cell_text in enumerate(row):
                            if cell_text is None:
                                cell_text = ""
                            cells.append({
                                "rowIndex": r_idx,
                                "columnIndex": c_idx,
                                "text": str(cell_text).strip(),
                            })
                    
                    if cells:
                        tables_out.append({
                            "rowCount": row_count,
                            "columnCount": col_count,
                            "cells": cells,
                            "boundingRegions": [{"pageNumber": page_num}],
                        })
    except Exception as e:
        print(f"[Inference] Table extraction failed: {e}")

    return tables_out


def filter_page_range(pages: List[Dict], page_range: str) -> List[Dict]:
    """Filter pages by range string like '1-3,5'."""
    wanted = set()
    for part in page_range.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-")
            wanted.update(range(int(start), int(end) + 1))
        elif part.isdigit():
            wanted.add(int(part))
    return [p for p in pages if p["page_number"] in wanted]
