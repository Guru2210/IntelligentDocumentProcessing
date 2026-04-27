"""
Table Structure Recognition using Microsoft Table Transformer (TATR).

Returns supervised bounding boxes for table rows and columns in PIXEL coordinates
matching the OCR word coordinate system. No unsupervised ML anywhere.

Model: microsoft/table-transformer-structure-recognition
Classes: table, table column, table row, table column header,
         table projected row header, table spanning cell
"""
import torch
from transformers import TableTransformerForObjectDetection, DetrImageProcessor
from PIL import Image
import io
import base64
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class TATRTableExtractor:
    """Singleton wrapper for the Table Transformer model."""
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.model_name = "microsoft/table-transformer-structure-recognition"
        self.processor = None
        self.model = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def _load_model(self):
        if self.processor is None or self.model is None:
            logger.info(f"[TATR] Loading {self.model_name} to {self.device}...")
            self.processor = DetrImageProcessor.from_pretrained(self.model_name)
            self.model = TableTransformerForObjectDetection.from_pretrained(self.model_name)
            self.model.to(self.device)
            self.model.eval()
            logger.info("[TATR] Model loaded successfully.")

    def detect_structure(
        self,
        image_b64: str,
        page_width: float,
        page_height: float,
        confidence_threshold: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Run TATR on a base64-encoded page image.

        Returns bounding boxes in the **OCR coordinate space** (PDF points),
        NOT in pixel or 0-1000 normalized space.

        Args:
            image_b64: base64-encoded PNG image of the page
            page_width: OCR page width (PDF points)
            page_height: OCR page height (PDF points)
            confidence_threshold: minimum detection confidence

        Returns:
            {
                "columns": [{"box": [x0,y0,x1,y1], "score": float}, ...],  # sorted left-to-right
                "rows":    [{"box": [x0,y0,x1,y1], "score": float}, ...],  # sorted top-to-bottom
            }
            All coordinates are in OCR/PDF-point space.
        """
        self._load_model()

        image_data = base64.b64decode(image_b64)
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        img_w, img_h = image.width, image.height

        # Scale factors: convert TATR pixel coords → OCR point coords
        scale_x = page_width / img_w
        scale_y = page_height / img_h

        target_size = torch.tensor([[img_h, img_w]])
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)

        results = self.processor.post_process_object_detection(
            outputs, threshold=confidence_threshold, target_sizes=target_size.to(self.device)
        )[0]

        cols: List[Dict] = []
        rows: List[Dict] = []

        for score, label, box in zip(results["scores"], results["labels"], results["boxes"]):
            box_px = box.cpu().tolist()  # pixel coordinates
            label_name = self.model.config.id2label[label.item()]

            # Convert to OCR coordinate space (PDF points)
            ocr_box = [
                box_px[0] * scale_x,
                box_px[1] * scale_y,
                box_px[2] * scale_x,
                box_px[3] * scale_y,
            ]

            entry = {"box": ocr_box, "score": round(score.item(), 3)}

            if label_name == "table column":
                cols.append(entry)
            elif label_name == "table row":
                rows.append(entry)

        # Sort: columns left-to-right, rows top-to-bottom
        cols.sort(key=lambda c: c["box"][0])
        rows.sort(key=lambda r: r["box"][1])

        logger.info(f"[TATR] Detected {len(cols)} columns, {len(rows)} rows")
        return {"columns": cols, "rows": rows}


def extract_table_grid(
    image_b64: str,
    page_width: float,
    page_height: float,
    confidence_threshold: float = 0.5,
) -> Dict[str, Any]:
    """
    Public API: detect table structure for a page image.
    Returns column/row bounding boxes in OCR coordinate space.
    """
    extractor = TATRTableExtractor.get_instance()
    return extractor.detect_structure(
        image_b64, page_width, page_height, confidence_threshold
    )
