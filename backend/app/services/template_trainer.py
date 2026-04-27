"""
Template Model Trainer — rule-based spatial anchor model.
No GPU required. Works on CPU in seconds.

Algorithm:
1. Load all labeled documents for a project
2. For each field, collect the normalized bounding boxes across all training docs
3. Compute average/median position per field → spatial anchor
4. Store as JSON model artifact

Inference:
1. Run OCR on new document
2. For each field anchor, find words whose bounding box overlaps the anchor region (with tolerance)
3. Return matched text as field value
"""
import json
import os
import uuid
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

import numpy as np
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Field, Label, Document, Page, Word, FieldType


def normalize_bbox(x0, y0, x1, y1, page_width, page_height) -> Tuple[float, float, float, float]:
    """Normalize bounding box to 0-1 range."""
    return (
        x0 / page_width,
        y0 / page_height,
        x1 / page_width,
        y1 / page_height,
    )


def iou(box_a: List[float], box_b: List[float]) -> float:
    """Compute Intersection Over Union of two [x0,y0,x1,y1] boxes."""
    xa = max(box_a[0], box_b[0])
    ya = max(box_a[1], box_b[1])
    xb = min(box_a[2], box_b[2])
    yb = min(box_a[3], box_b[3])
    inter = max(0, xb - xa) * max(0, yb - ya)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def bbox_overlap_ratio(box_a: List[float], box_b: List[float]) -> float:
    """What fraction of box_a overlaps with box_b."""
    xa = max(box_a[0], box_b[0])
    ya = max(box_a[1], box_b[1])
    xb = min(box_a[2], box_b[2])
    yb = min(box_a[3], box_b[3])
    inter = max(0, xb - xa) * max(0, yb - ya)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    return inter / area_a if area_a > 0 else 0.0


def train_template_model(
    project_id: str,
    db: Session,
    log_callback=None,
) -> Dict[str, Any]:
    """
    Train a template (spatial anchor) model for a project.
    Returns the model artifact dict.
    """
    def log(msg: str):
        if log_callback:
            log_callback(msg)

    log("Loading project fields...")
    fields: List[Field] = db.query(Field).filter(Field.project_id == project_id).all()
    
    # Get labeled documents
    documents: List[Document] = (
        db.query(Document)
        .filter(Document.project_id == project_id)
        .filter(Document.label_status == "complete")
        .all()
    )
    log(f"Found {len(documents)} labeled documents, {len(fields)} fields")

    field_anchors = {}  # field_id -> list of label instances

    for doc in documents:
        pages_map = {p.page_number: p for p in doc.pages}
        labels: List[Label] = db.query(Label).filter(Label.document_id == doc.id).all()

        for label in labels:
            field_id = str(label.field_id)
            page = pages_map.get(label.page_number)
            if not page:
                continue

            pw, ph = page.width, page.height
            boxes = label.bounding_boxes or []
            if not boxes:
                continue

            norm_boxes = []
            for box in boxes:
                if len(box) == 4:
                    nx0, ny0, nx1, ny1 = normalize_bbox(box[0], box[1], box[2], box[3], pw, ph)
                elif len(box) == 8:
                    # polygon [x0,y0,x1,y1,x2,y2,x3,y3]
                    xs = box[0::2]
                    ys = box[1::2]
                    nx0, ny0, nx1, ny1 = normalize_bbox(min(xs), min(ys), max(xs), max(ys), pw, ph)
                else:
                    continue
                norm_boxes.append([nx0, ny0, nx1, ny1])

            if field_id not in field_anchors:
                field_anchors[field_id] = []

            entry = {
                "page": label.page_number,
                "boxes": norm_boxes,
                "text": label.text or "",
                "row_index": label.row_index,
                "column_name": label.column_name,
            }
            field_anchors[field_id].append(entry)

    # Build model artifact
    model_artifact = {
        "model_type": "template",
        "project_id": project_id,
        "fields": {},
    }

    for field in fields:
        fid = str(field.id)
        anchors = field_anchors.get(fid, [])
        log(f"  Field '{field.name}': {len(anchors)} label instances")

        if field.field_type == "table":
            # For table fields, collect column-specific spatial anchors
            col_anchors: Dict[str, List] = {}
            for a in anchors:
                col = a.get("column_name")
                if col:
                    if col not in col_anchors:
                        col_anchors[col] = []
                    col_anchors[col].extend(a["boxes"])

            computed_cols = {}
            for col, boxes in col_anchors.items():
                if boxes:
                    arr = np.array(boxes)
                    computed_cols[col] = {
                        "mean_box": arr.mean(axis=0).tolist(),
                        "std_box": arr.std(axis=0).tolist(),
                        "tolerance": 0.08,
                    }

            model_artifact["fields"][field.name] = {
                "field_type": "table",
                "data_type": field.data_type,
                "columns": computed_cols,
                "page_anchors": _compute_page_distribution(anchors),
            }
        else:
            # Text / checkbox / signature fields
            all_boxes = []
            for a in anchors:
                all_boxes.extend(a["boxes"])

            if all_boxes:
                arr = np.array(all_boxes)
                mean_box = arr.mean(axis=0).tolist()
                std_box = arr.std(axis=0).tolist()
            else:
                mean_box = [0, 0, 1, 1]
                std_box = [0.5, 0.5, 0.5, 0.5]

            model_artifact["fields"][field.name] = {
                "field_type": field.field_type,
                "data_type": field.data_type,
                "mean_box": mean_box,
                "std_box": std_box,
                "tolerance": 0.06,
                "page_anchors": _compute_page_distribution(anchors),
                "sample_values": [a["text"] for a in anchors[:5]],
            }

    return model_artifact


def _compute_page_distribution(anchors: List[Dict]) -> Dict:
    """Determine which pages a field appears on, and with what frequency."""
    page_counts = {}
    for a in anchors:
        p = a.get("page", 1)
        page_counts[str(p)] = page_counts.get(str(p), 0) + 1
    if not page_counts:
        return {"most_common_page": 1}
    most_common = max(page_counts, key=page_counts.get)
    return {"most_common_page": int(most_common), "page_distribution": page_counts}


def run_template_inference(
    model_artifact: Dict,
    ocr_pages: List[Dict],
    confidence_threshold: float = 0.0,
) -> Dict[str, Any]:
    """
    Run inference using a template model.
    
    ocr_pages: list of dicts with keys: page_number, width, height, words
    Returns extracted fields with values and confidence scores.
    """
    results = {}
    field_defs = model_artifact.get("fields", {})

    for field_name, field_def in field_defs.items():
        field_type = field_def.get("field_type", "text")
        most_common_page = field_def.get("page_anchors", {}).get("most_common_page", 1)

        # Find the right page
        target_page = None
        for page in ocr_pages:
            if page["page_number"] == most_common_page:
                target_page = page
                break
        if not target_page:
            target_page = ocr_pages[0] if ocr_pages else None

        if not target_page:
            continue

        pw = target_page["width"]
        ph = target_page["height"]
        words = target_page.get("words", [])

        if field_type == "table":
            # Extract table cells
            col_defs = field_def.get("columns", {})
            table_rows: Dict[int, Dict] = {}

            for word in words:
                wx0, wy0, wx1, wy1 = word["x0"], word["y0"], word["x1"], word["y1"]
                norm_word = normalize_bbox(wx0, wy0, wx1, wy1, pw, ph)

                for col_name, col_anchor in col_defs.items():
                    mean_box = col_anchor["mean_box"]
                    tol = col_anchor.get("tolerance", 0.08)
                    expanded_box = [
                        mean_box[0] - tol,
                        mean_box[1] - tol,
                        mean_box[2] + tol,
                        mean_box[3] + tol,
                    ]
                    overlap = bbox_overlap_ratio(list(norm_word), expanded_box)
                    if overlap > 0.3:
                        # Determine row by y-position relative to anchor box
                        row_height = (mean_box[3] - mean_box[1])
                        row_idx = max(0, int((norm_word[1] - mean_box[1]) / row_height)) if row_height > 0 else 0
                        if row_idx not in table_rows:
                            table_rows[row_idx] = {}
                        if col_name not in table_rows[row_idx]:
                            table_rows[row_idx][col_name] = {"text": "", "confidence": 0.0, "count": 0}
                        table_rows[row_idx][col_name]["text"] += (" " + word["text"]).strip()
                        table_rows[row_idx][col_name]["confidence"] += word.get("confidence", 1.0)
                        table_rows[row_idx][col_name]["count"] += 1

            # Finalize table rows
            rows_list = []
            for row_idx in sorted(table_rows.keys()):
                row_data = {}
                for col_name, cell in table_rows[row_idx].items():
                    count = max(cell["count"], 1)
                    row_data[col_name] = {
                        "type": "string",
                        "valueString": cell["text"].strip(),
                        "confidence": round(cell["confidence"] / count, 3),
                    }
                if row_data:
                    rows_list.append({"type": "object", "valueObject": row_data})

            results[field_name] = {
                "type": "array",
                "valueArray": rows_list,
                "confidence": round(
                    np.mean([
                        cell["confidence"] / max(cell["count"], 1)
                        for row in table_rows.values()
                        for cell in row.values()
                    ]) if table_rows else 0.0, 3
                ),
            }

        else:
            # Text / checkbox / signature
            mean_box = field_def.get("mean_box", [0, 0, 1, 1])
            tol = field_def.get("tolerance", 0.06)
            data_type = field_def.get("data_type", "string")

            expanded_box = [
                max(0, mean_box[0] - tol),
                max(0, mean_box[1] - tol),
                min(1, mean_box[2] + tol),
                min(1, mean_box[3] + tol),
            ]

            matched_words = []
            for word in words:
                wx0, wy0, wx1, wy1 = word["x0"], word["y0"], word["x1"], word["y1"]
                norm_word = list(normalize_bbox(wx0, wy0, wx1, wy1, pw, ph))
                overlap = bbox_overlap_ratio(norm_word, expanded_box)
                if overlap > 0.4:
                    matched_words.append(word)

            # Sort by reading order (top-to-bottom, left-to-right)
            matched_words.sort(key=lambda w: (w["y0"], w["x0"]))
            extracted_text = " ".join(w["text"] for w in matched_words).strip()

            if matched_words:
                avg_conf = np.mean([w.get("confidence", 1.0) for w in matched_words])
            else:
                avg_conf = 0.0

            value_key, value = _format_value(extracted_text, data_type)
            results[field_name] = {
                "type": data_type if data_type != "string" else "string",
                value_key: value,
                "confidence": round(float(avg_conf), 3),
                "boundingRegions": [
                    {
                        "pageNumber": most_common_page,
                        "polygon": [
                            min(w["x0"] for w in matched_words) if matched_words else 0,
                            min(w["y0"] for w in matched_words) if matched_words else 0,
                            max(w["x1"] for w in matched_words) if matched_words else 0,
                            max(w["y1"] for w in matched_words) if matched_words else 0,
                        ],
                    }
                ] if matched_words else [],
            }

    return results


def _format_value(text: str, data_type: str):
    """Format extracted text to the correct value type and key."""
    if not text:
        return "valueString", ""

    if data_type == "number":
        try:
            cleaned = text.replace(",", "").replace("$", "").replace("€", "").strip()
            return "valueNumber", float(cleaned)
        except ValueError:
            return "valueString", text
    elif data_type == "integer":
        try:
            return "valueInteger", int(text.replace(",", "").strip())
        except ValueError:
            return "valueString", text
    elif data_type == "date":
        return "valueDate", text
    elif data_type == "selectionMark":
        lower = text.lower()
        state = "selected" if any(x in lower for x in ["x", "✓", "✔", "checked", "yes"]) else "unselected"
        return "valueSelectionMark", state
    else:
        return "valueString", text


def save_model_artifact(model_artifact: Dict, project_id: str, version: int) -> str:
    """Save model JSON to disk, returns model_path."""
    model_dir = Path(settings.models_dir) / project_id / f"v{version}"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "template_model.json"
    with open(model_path, "w") as f:
        json.dump(model_artifact, f, indent=2)
    return str(model_path)


def load_model_artifact(model_path: str) -> Dict:
    """Load model JSON from disk."""
    with open(model_path, "r") as f:
        return json.load(f)
