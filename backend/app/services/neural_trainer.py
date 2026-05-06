"""
LayoutLMv3 Neural Model Trainer.
Fine-tunes microsoft/layoutlmv3-base on project-specific labeled data.
Uses BIO (Begin-Inside-Outside) token classification.
"""
import json
import os
import logging
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)


def normalize_bbox_1000(x0, y0, x1, y1, page_width, page_height) -> List[int]:
    """Normalize bounding box to 0-1000 scale (LayoutLM requirement)."""
    return [
        max(0, min(1000, int(x0 * 1000 / page_width))),
        max(0, min(1000, int(y0 * 1000 / page_height))),
        max(0, min(1000, int(x1 * 1000 / page_width))),
        max(0, min(1000, int(y1 * 1000 / page_height))),
    ]


def build_bio_dataset(
    labeled_documents: List[Dict],
    label_map: Dict[str, int],
    log: Callable = print,
) -> List[Dict]:
    """
    Build BIO-tagged dataset from labeled documents.
    
    labeled_documents: list of {words, labels, page_width, page_height}
    label_map: {"O": 0, "B-invoice_number": 1, "I-invoice_number": 2, ...}
    """
    dataset = []
    
    for doc in labeled_documents:
        words = doc["words"]
        labels_data = doc["labels"]  # list of {field_name, word_indices, text}
        pw = doc["page_width"]
        ph = doc["page_height"]

        # Build word_id -> tag mapping
        word_tags = {}
        for label_entry in labels_data:
            field_name = label_entry["field_name"]
            word_indices = label_entry.get("word_indices", [])
            for i, word_idx in enumerate(word_indices):
                if i == 0:
                    tag = f"B-{field_name}"
                else:
                    tag = f"I-{field_name}"
                word_tags[word_idx] = tag

        chunk_size = 150
        for chunk_start in range(0, len(words), chunk_size):
            chunk_words = words[chunk_start:chunk_start+chunk_size]
            tokens = []
            bboxes = []
            bio_labels = []

            for i, word in enumerate(chunk_words):
                global_i = chunk_start + i
                text = word["text"]
                x0, y0, x1, y1 = word["x0"], word["y0"], word["x1"], word["y1"]
                bbox = normalize_bbox_1000(x0, y0, x1, y1, pw, ph)
                tag = word_tags.get(global_i, "O")
                label_id = label_map.get(tag, label_map.get("O", 0))

                tokens.append(text)
                bboxes.append(bbox)
                bio_labels.append(label_id)

            if tokens:
                dataset.append({
                    "tokens": tokens,
                    "bboxes": bboxes,
                    "labels": bio_labels,
                })

    return dataset


def train_neural_model(
    project_id: str,
    labeled_documents: List[Dict],
    field_names: List[str],
    model_dir: str,
    log_callback: Optional[Callable] = None,
    epochs: int = 10,
    learning_rate: float = 1e-5,
    batch_size: int = 2,
) -> Dict[str, Any]:
    """
    Fine-tune LayoutLMv3 for token classification.
    Returns metrics dict.
    """
    def log(msg: str):
        if log_callback:
            log_callback(msg)
        logger.info(msg)

    log("Importing ML dependencies...")
    try:
        import torch
        from transformers import (
            LayoutLMv3ForTokenClassification,
            LayoutLMv3Processor,
            LayoutLMv3TokenizerFast,
            AdamW,
            get_linear_schedule_with_warmup,
        )
        from torch.utils.data import Dataset, DataLoader
        from sklearn.model_selection import train_test_split
    except ImportError as e:
        raise RuntimeError(f"ML dependencies not installed: {e}")

    # Build label map
    label_list = ["O"]
    for fn in field_names:
        label_list.append(f"B-{fn}")
        label_list.append(f"I-{fn}")
    label_map = {label: idx for idx, label in enumerate(label_list)}
    id2label = {idx: label for label, idx in label_map.items()}
    num_labels = len(label_list)

    log(f"Label classes: {num_labels} ({label_list[:6]}...)")

    # Build dataset
    log(f"Building BIO-tagged dataset from {len(labeled_documents)} documents...")
    bio_data = build_bio_dataset(labeled_documents, label_map, log)

    if len(bio_data) < 2:
        log("WARNING: Very few training examples. Results may be poor.")
        train_data = bio_data
        val_data = bio_data
    else:
        split = max(1, int(len(bio_data) * 0.8))
        train_data = bio_data[:split]
        val_data = bio_data[split:] if split < len(bio_data) else bio_data[-1:]

    log(f"Train: {len(train_data)} docs, Val: {len(val_data)} docs")

    log("Loading LayoutLMv3-base tokenizer...")
    try:
        tokenizer = LayoutLMv3TokenizerFast.from_pretrained("microsoft/layoutlmv3-base")
    except Exception:
        log("Failed to load from HuggingFace Hub. Ensure internet access on first run.")
        raise

    class IDPDataset(Dataset):
        def __init__(self, data, tokenizer, max_length=512):
            self.data = data
            self.tokenizer = tokenizer
            self.max_length = max_length

        def __len__(self):
            return len(self.data)

        def __getitem__(self, idx):
            item = self.data[idx]
            tokens = item["tokens"][:self.max_length - 2]
            bboxes = item["bboxes"][:self.max_length - 2]
            labels = item["labels"][:self.max_length - 2]

            encoding = self.tokenizer(
                tokens,
                boxes=bboxes,
                word_labels=labels,
                truncation=True,
                padding="max_length",
                max_length=self.max_length,
                return_tensors="pt",
            )
            return {k: v.squeeze(0) for k, v in encoding.items()}

    train_dataset = IDPDataset(train_data, tokenizer)
    val_dataset = IDPDataset(val_data, tokenizer)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size)

    log("Loading LayoutLMv3ForTokenClassification model...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log(f"Device: {device}")

    model = LayoutLMv3ForTokenClassification.from_pretrained(
        "microsoft/layoutlmv3-base",
        num_labels=num_labels,
        id2label=id2label,
        label2id=label_map,
    )
    model.to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    total_steps = len(train_loader) * epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=total_steps // 10, num_training_steps=total_steps
    )

    epoch_losses = []
    field_f1_history = []
    best_val_loss = float("inf")

    for epoch in range(epochs):
        model.train()
        total_loss = 0
        for batch in train_loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            outputs = model(**batch)
            loss = outputs.loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()
            total_loss += loss.item()

        avg_loss = total_loss / max(len(train_loader), 1)
        epoch_losses.append(avg_loss)

        # Validation
        model.eval()
        val_loss = 0
        all_preds = []
        all_true = []
        with torch.no_grad():
            for batch in val_loader:
                batch = {k: v.to(device) for k, v in batch.items()}
                outputs = model(**batch)
                val_loss += outputs.loss.item()
                preds = torch.argmax(outputs.logits, dim=-1)
                labels_batch = batch["labels"]
                mask = labels_batch != -100
                all_preds.extend(preds[mask].cpu().numpy().tolist())
                all_true.extend(labels_batch[mask].cpu().numpy().tolist())

        avg_val_loss = val_loss / max(len(val_loader), 1)

        # Compute per-field F1
        field_f1 = _compute_field_f1(all_preds, all_true, label_list, id2label)
        overall_f1 = np.mean(list(field_f1.values())) if field_f1 else 0.0
        field_f1_history.append(field_f1)

        log(f"Epoch {epoch+1}/{epochs} — loss: {avg_loss:.4f} — val_loss: {avg_val_loss:.4f} — field_f1: {overall_f1:.3f}")

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            # Save checkpoint
            checkpoint_dir = os.path.join(model_dir, "checkpoint-best")
            model.save_pretrained(checkpoint_dir)
            tokenizer.save_pretrained(checkpoint_dir)

    # Save final model
    final_dir = os.path.join(model_dir, "layoutlmv3-finetuned")
    model.save_pretrained(final_dir)
    tokenizer.save_pretrained(final_dir)

    # Save label map
    with open(os.path.join(final_dir, "label_map.json"), "w") as f:
        json.dump({"label_list": label_list, "label_map": label_map, "id2label": id2label}, f)

    final_f1 = field_f1_history[-1] if field_f1_history else {}
    overall_f1 = float(np.mean(list(final_f1.values()))) if final_f1 else 0.0

    log(f"Training complete. Overall F1: {overall_f1:.3f}")
    return {
        "epoch_losses": epoch_losses,
        "field_f1": final_f1,
        "overall_f1": overall_f1,
        "model_path": final_dir,
        "label_list": label_list,
    }


def _compute_field_f1(preds, trues, label_list, id2label) -> Dict[str, float]:
    """Compute per-field F1 scores from flat prediction/true arrays."""
    from collections import defaultdict
    field_tp = defaultdict(int)
    field_fp = defaultdict(int)
    field_fn = defaultdict(int)

    for p, t in zip(preds, trues):
        pred_label = id2label.get(p, "O")
        true_label = id2label.get(t, "O")

        pred_field = pred_label.split("-", 1)[1] if "-" in pred_label else None
        true_field = true_label.split("-", 1)[1] if "-" in true_label else None

        if pred_field and pred_field == true_field:
            field_tp[pred_field] += 1
        elif pred_field and pred_field != true_field:
            field_fp[pred_field] += 1
            if true_field:
                field_fn[true_field] += 1
        elif true_field:
            field_fn[true_field] += 1

    f1_scores = {}
    all_fields = set(field_tp.keys()) | set(field_fp.keys()) | set(field_fn.keys())
    for field in all_fields:
        tp = field_tp[field]
        fp = field_fp[field]
        fn = field_fn[field]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        f1_scores[field] = round(f1, 3)

    return f1_scores


def run_neural_inference(
    model_path: str,
    ocr_pages: List[Dict],
    field_names: List[str],
    field_types: Optional[Dict[str, str]] = None,
    field_columns: Optional[Dict[str, List[str]]] = None,
    field_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run LayoutLMv3 inference on OCR output.
    field_types: {field_name: "table" | "text" | ...} — used to produce valueArray for table fields.
    """
    import torch
    import numpy as np
    from transformers import LayoutLMv3ForTokenClassification, LayoutLMv3TokenizerFast

    field_types = field_types or {}
    label_map_path = os.path.join(model_path, "label_map.json")
    with open(label_map_path) as f:
        lm = json.load(f)
    id2label = {int(k): v for k, v in lm["id2label"].items()}

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = LayoutLMv3TokenizerFast.from_pretrained(model_path)
    model = LayoutLMv3ForTokenClassification.from_pretrained(model_path)
    model.to(device)
    model.eval()

    # Accumulate tokens per field across all pages
    all_field_tokens: Dict[str, List] = {fn: [] for fn in field_names}

    for page_data in ocr_pages:
        words = page_data.get("words", [])
        pw = page_data["width"]
        ph = page_data["height"]
        page_num = page_data["page_number"]

        if not words:
            continue

        chunk_size = 150
        word_predictions = {}
        for chunk_start in range(0, len(words), chunk_size):
            chunk_words = words[chunk_start:chunk_start+chunk_size]
            tokens = [w["text"] for w in chunk_words]
            bboxes = [normalize_bbox_1000(w["x0"], w["y0"], w["x1"], w["y1"], pw, ph) for w in chunk_words]

            encoding = tokenizer(
                tokens,
                boxes=bboxes,
                truncation=True,
                padding="max_length",
                max_length=512,
                return_tensors="pt",
                return_offsets_mapping=True,
            )
            offset_mapping = encoding.pop("offset_mapping")

            with torch.no_grad():
                outputs = model(**{k: v.to(device) for k, v in encoding.items()})

            logits = outputs.logits.squeeze(0)
            probs = torch.softmax(logits, dim=-1)
            predicted_ids = torch.argmax(logits, dim=-1)

            # Map tokens back to chunks, then global idx
            for token_idx, (word_idx_in_chunk, label_id) in enumerate(
                zip(encoding.word_ids(0), predicted_ids.cpu().numpy())
            ):
                if word_idx_in_chunk is None or word_idx_in_chunk >= len(chunk_words):
                    continue
                global_word_idx = chunk_start + word_idx_in_chunk
                label = id2label.get(int(label_id), "O")
                conf = float(probs[token_idx, int(label_id)])
                if global_word_idx not in word_predictions:
                    word_predictions[global_word_idx] = (label, conf)

        # Aggregate by field keeping per-word detail
        current_field = None
        field_tokens: Dict[str, List] = {fn: [] for fn in field_names}

        for word_idx in sorted(word_predictions.keys()):
            label, conf = word_predictions[word_idx]
            if label.startswith("B-"):
                current_field = label[2:]
            elif label.startswith("I-") and current_field == label[2:]:
                pass
            else:
                current_field = None

            if current_field and current_field in field_tokens:
                field_tokens[current_field].append({
                    "text": words[word_idx]["text"],
                    "confidence": conf,
                    "bbox": [words[word_idx]["x0"], words[word_idx]["y0"],
                             words[word_idx]["x1"], words[word_idx]["y1"]],
                    "page": page_num,
                })

        for fn, ftokens in field_tokens.items():
            all_field_tokens[fn].extend(ftokens)

    # Build results
    results: Dict[str, Any] = {}
    for fn in field_names:
        ftokens = all_field_tokens[fn]
        ftype = field_types.get(fn, "text")

        if not ftokens:
            if ftype == "table":
                results[fn] = {"type": "array", "valueArray": [], "confidence": 0.0}
            else:
                results[fn] = {"type": "string", "valueString": "", "confidence": 0.0}
            continue

        avg_conf = round(float(np.mean([t["confidence"] for t in ftokens])), 3)

        if ftype == "table":
            # ── SUPERVISED TABLE EXTRACTION (TATR + LayoutLMv3) ──
            # LayoutLMv3 identified WHICH words belong to this table field.
            # TATR identifies the physical grid (rows + columns) from the page image.
            # We intersect them deterministically — zero unsupervised ML.

            ftokens_sorted = sorted(ftokens, key=lambda t: (t["page"], t["bbox"][1], t["bbox"][0]))
            expected_cols = field_columns.get(fn, []) if field_columns else []
            num_cols = len(expected_cols) if expected_cols else 1

            # ── Step 1: Run TATR on each page to get supervised grid ──
            from app.services.table_extractor import extract_table_grid

            page_grids: Dict[int, Dict] = {}
            for p_data in ocr_pages:
                p_num = p_data["page_number"]
                if "image_b64" in p_data:
                    try:
                        grid = extract_table_grid(
                            p_data["image_b64"],
                            page_width=p_data["width"],
                            page_height=p_data["height"],
                        )
                        page_grids[p_num] = grid
                        print(f"[TATR] Page {p_num}: {len(grid.get('columns',[]))} cols, {len(grid.get('rows',[]))} rows")
                    except Exception as e:
                        print(f"[TATR] Failed on page {p_num}: {e}")

            # ── Step 1b: Load supervised column boundaries (learned during training) ──
            supervised_boundaries = None
            supervised_config = None
            if model_path:
                bounds_file = os.path.join(model_path, "column_boundaries.json")
                if os.path.exists(bounds_file):
                    try:
                        with open(bounds_file, "r") as f:
                            bounds_data = json.load(f)
                            if fn in bounds_data:
                                supervised_config = bounds_data[fn]
                                supervised_boundaries = supervised_config.get("boundaries", [])
                                print(f"Loaded supervised boundaries for {fn}")
                    except Exception as e:
                        print(f"Error loading boundaries: {e}")

            # ── Step 1c: Compute a consistent fallback grid ──
            fallback_cols = []
            for g in page_grids.values():
                c = g.get("columns", [])
                if len(c) > len(fallback_cols):
                    fallback_cols = c

            # ── Step 2: Helper functions ──
            def _find_containing_box(center: float, boxes: List[Dict], axis: str) -> int:
                if not boxes:
                    return 0
                coord_idx = 0 if axis == "x" else 1
                coord_end = 2 if axis == "x" else 3

                for i, b in enumerate(boxes):
                    if b["box"][coord_idx] <= center <= b["box"][coord_end]:
                        return i

                best_i = 0
                best_dist = float("inf")
                for i, b in enumerate(boxes):
                    box_center = (b["box"][coord_idx] + b["box"][coord_end]) / 2.0
                    dist = abs(center - box_center)
                    if dist < best_dist:
                        best_dist = dist
                        best_i = i
                return best_i

            def _map_tatr_col_to_schema(tatr_col_idx: int, tatr_col_count: int, schema_col_count: int) -> int:
                if tatr_col_count == schema_col_count:
                    return tatr_col_idx
                if tatr_col_count == 0 or schema_col_count == 0:
                    return 0
                return min(int(tatr_col_idx * schema_col_count / tatr_col_count), schema_col_count - 1)

            # ── Step 3: Assign row_idx and col_idx to each token ──
            global_row_counter = 0
            last_page = None

            table_meta = (field_metadata or {}).get(fn, {})
            table_mode = table_meta.get("table_mode", "normal")

            for tok in ftokens_sorted:
                p_num = tok["page"]
                grid = page_grids.get(p_num, {})
                tatr_rows = grid.get("rows", [])
                tatr_cols = grid.get("columns", [])
                p_data = next((p for p in ocr_pages if p["page_number"] == p_num), None)
                pw = p_data["width"] if p_data else 1000.0

                mid_y = (tok["bbox"][1] + tok["bbox"][3]) / 2.0
                mid_x = (tok["bbox"][0] + tok["bbox"][2]) / 2.0
                nx = mid_x / pw
                tok["nx"] = nx  # Save normalized X for advanced table boundary filtering

                # Assign row using per-page TATR supervised row boxes
                if tatr_rows:
                    page_row_idx = _find_containing_box(mid_y, tatr_rows, "y")
                    if last_page is not None and p_num != last_page:
                        prev_row_indices = set(
                            t.get("row_idx", 0) for t in ftokens_sorted
                            if t["page"] < p_num and "row_idx" in t
                        )
                        global_row_counter = max(prev_row_indices) + 1 if prev_row_indices else global_row_counter
                    tok["row_idx"] = global_row_counter + page_row_idx
                else:
                    tok["row_idx"] = -1

                last_page = p_num

                # Assign column (for normal tables only; advanced uses nx later)
                if table_mode == "normal":
                    if num_cols > 1:
                        if supervised_boundaries: 
                            col_idx = 0
                            for b in supervised_boundaries:
                                if nx > b:
                                    col_idx += 1
                            tok["col_idx"] = min(col_idx, num_cols - 1)
                        else:
                            best_cols = fallback_cols if fallback_cols else tatr_cols
                            if best_cols:
                                best_idx = _find_containing_box(mid_x, best_cols, "x")
                                tok["col_idx"] = _map_tatr_col_to_schema(best_idx, len(best_cols), num_cols)
                            else:
                                tok["col_idx"] = 0
                    else:
                        tok["col_idx"] = 0

            # ── Step 3b: Fix tokens without TATR row assignment (Y-proximity) ──
            unassigned = [t for t in ftokens_sorted if t.get("row_idx", -1) == -1]
            if unassigned:
                row_gap = 10  # points
                current_row_idx = global_row_counter + 1
                last_y = None
                for tok in sorted(unassigned, key=lambda t: (t["page"], t["bbox"][1])):
                    y0 = tok["bbox"][1]
                    if last_y is not None and abs(y0 - last_y) > row_gap:
                        current_row_idx += 1
                    tok["row_idx"] = current_row_idx
                    last_y = y0

            # ── Step 4: Group by row → build structured output ──
            from collections import defaultdict
            row_groups: Dict[int, List] = defaultdict(list)
            for tok in ftokens_sorted:
                row_groups[tok.get("row_idx", 0)].append(tok)

            value_array = []

            if table_mode == "advanced":
                # ── ADVANCED TABLE: Group physical rows into logical records ──
                rows_per_record = table_meta.get("rows_per_record", 1)
                col_row_levels = table_meta.get("col_row_levels", {})
                physical_row_indices = sorted(row_groups.keys())
                
                logical_records = [physical_row_indices[i:i + rows_per_record] 
                                   for i in range(0, len(physical_row_indices), rows_per_record)]
                
                for record_rows in logical_records:
                    obj_data = {}
                    has_content = False
                    
                    for col_name in expected_cols:
                        sub_row_idx = col_row_levels.get(col_name, 0)
                        c_toks = []
                        
                        if sub_row_idx < len(record_rows):
                            p_row_idx = record_rows[sub_row_idx]
                            p_toks = row_groups[p_row_idx]
                            
                            if supervised_config and "row_levels" in supervised_config:
                                rl_config = supervised_config["row_levels"].get(str(sub_row_idx), {})
                                rl_cols = rl_config.get("columns", [])
                                rl_bounds = rl_config.get("boundaries", [])
                                
                                try:
                                    local_col_idx = rl_cols.index(col_name)
                                except ValueError:
                                    local_col_idx = 0
                                
                                # Filter tokens by X boundaries for this specific column in this sub-row
                                for t in p_toks:
                                    t_col_idx = 0
                                    for b in rl_bounds:
                                        if t["nx"] > b:
                                            t_col_idx += 1
                                    
                                    if t_col_idx == local_col_idx:
                                        c_toks.append(t)
                            else:
                                # Fallback: put everything in the first matching column for the row_level if no bounds
                                if col_name == next((c for c in expected_cols if col_row_levels.get(c, 0) == sub_row_idx), None):
                                    c_toks = p_toks

                        if c_toks:
                            c_toks.sort(key=lambda t: t["bbox"][0])
                            c_text = " ".join(t["text"] for t in c_toks).strip()
                            c_conf = round(float(np.mean([t["confidence"] for t in c_toks])), 3)
                            obj_data[col_name] = {
                                "type": "string",
                                "valueString": c_text,
                                "confidence": c_conf,
                            }
                            has_content = True
                        else:
                            obj_data[col_name] = {
                                "type": "string",
                                "valueString": "",
                                "confidence": 0.0,
                            }
                            
                    if has_content:
                        value_array.append({
                            "type": "object",
                            "valueObject": obj_data,
                        })

            else:
                # ── NORMAL TABLE: 1 Logical Record = 1 Physical Row ──
                for row_idx in sorted(row_groups.keys()):
                    row_toks = row_groups[row_idx]

                    if num_cols > 1 and expected_cols:
                        col_buckets: Dict[int, List] = {i: [] for i in range(num_cols)}
                        for t in row_toks:
                            ci = t.get("col_idx", 0)
                            ci = min(ci, num_cols - 1)
                            col_buckets[ci].append(t)

                        obj_data = {}
                        has_content = False
                        for i, col_name in enumerate(expected_cols):
                            if col_buckets[i]:
                                c_toks = sorted(col_buckets[i], key=lambda t: t["bbox"][0])
                                c_text = " ".join(t["text"] for t in c_toks).strip()
                                c_conf = round(float(np.mean([t["confidence"] for t in c_toks])), 3)
                                obj_data[col_name] = {
                                    "type": "string",
                                    "valueString": c_text,
                                    "confidence": c_conf,
                                }
                                has_content = True
                            else:
                                obj_data[col_name] = {
                                    "type": "string",
                                    "valueString": "",
                                    "confidence": 0.0,
                                }

                        if has_content:
                            value_array.append({
                                "type": "object",
                                "valueObject": obj_data,
                            })
                    else:
                        row_text = " ".join(t["text"] for t in row_toks).strip()
                        row_conf = round(float(np.mean([t["confidence"] for t in row_toks])), 3)
                        if row_text:
                            value_array.append({
                                "type": "object",
                                "valueObject": {
                                    fn: {
                                        "type": "string",
                                        "valueString": row_text,
                                        "confidence": row_conf,
                                    }
                                },
                            })

            results[fn] = {
                "type": "array",
                "valueArray": value_array,
                "confidence": avg_conf,
            }
        else:
            text = " ".join(t["text"] for t in ftokens)
            results[fn] = {
                "type": "string",
                "valueString": text,
                "confidence": avg_conf,
                "boundingRegions": [{
                    "pageNumber": ftokens[0]["page"],
                    "polygon": [
                        min(t["bbox"][0] for t in ftokens),
                        min(t["bbox"][1] for t in ftokens),
                        max(t["bbox"][2] for t in ftokens),
                        max(t["bbox"][3] for t in ftokens),
                    ],
                }],
            }

    return results
