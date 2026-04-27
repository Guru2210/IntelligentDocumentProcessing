# 🧠 IDP Studio — Self-Hosted Intelligent Document Processing

A complete, production-ready document intelligence platform equivalent to **Azure Document Intelligence** — fully self-hosted with no cloud dependencies.

---

## 🚀 Quick Start

### Prerequisites
- **Docker Desktop** installed and running
- **8GB RAM** minimum (16GB recommended for neural model training)
- **20GB disk space** for models and documents

### Start in One Command

```powershell
# Windows PowerShell
.\start.ps1
```

Or manually:

```bash
cp .env.example .env
docker compose up --build -d
```

### Access the System

| Service | URL |
|---------|-----|
| **Label Studio (Frontend)** | http://localhost:3000 |
| **API** | http://localhost:8000 |
| **API Docs (Swagger)** | http://localhost:8000/docs |
| **MinIO Console** | http://localhost:9001 (minioadmin / minioadmin123) |

---

## 📋 Full Workflow

### 1. Create a Project
- Go to **Projects** → New Project
- Choose a prebuilt schema (Invoice, Receipt, ID Document, Bank Statement) or define custom fields
- Select model type: **Template** (fast, CPU) or **Neural** (LayoutLMv3, accurate)

### 2. Upload Documents
- Go to **Documents** → select your project → drag & drop PDFs/images
- OCR runs automatically in the background (watch the status column)

### 3. Label Documents
- Go to **Label Studio** → select project + document
- **Click** a word to assign it to the active field
- **Shift+click** multiple words for a multi-word value
- For **table fields**: click a word → popup asks for row + column assignment
- Click **Save & Complete** when done with each document

### 4. Train Model
- Go to **Training** → select project → click **Train Model**
- Watch the real-time training log stream
- Template model trains in seconds; neural model takes 5-30 minutes

### 5. Extract from New Documents
- Go to **Extract** → select project + model → drop a new document
- Results appear with confidence scores per field
- Download as **JSON**, **CSV**, or **Excel**

### 6. Review Low-Confidence Extractions
- Go to **Review Queue** → see fields below confidence threshold (default 0.85)
- Accept, correct, or reject each prediction

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│          React Frontend (port 3000)              │
│  Projects │ Label Studio │ Train │ Extract │ Review │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│           FastAPI Backend (port 8000)            │
│  /api/v1/projects /documents /labels /train      │
│  /extract /models /review                        │
└──┬──────────┬────────────┬──────────┬────────────┘
   │          │            │          │
PostgreSQL  Redis +     MinIO       Models
(port 5432) Celery   (port 9000)  (./models/)
            Workers
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + Vite |
| Canvas/Labeling | Custom overlay with PDF.js |
| Charts | Recharts |
| Backend | FastAPI + Uvicorn |
| Task Queue | Celery + Redis |
| OCR (native PDF) | PyMuPDF (fitz) |
| OCR (scanned) | EasyOCR |
| Template model | Rule-based spatial matching |
| Neural model | LayoutLMv3 (microsoft/layoutlmv3-base) |
| Storage | MinIO (S3-compatible) |
| Database | PostgreSQL 15 |

---

## 🎯 Supported Field Types

| Type | Description |
|------|-------------|
| **Text** | Single or multi-word string values |
| **Table** | Variable-row tables with named columns |
| **Checkbox** | Selection mark detection (selected/unselected) |
| **Signature** | Presence/absence of signature regions |

## 📊 Data Types

`string`, `number`, `date`, `time`, `integer`, `selectionMark`, `countryRegion`, `phoneNumber`

---

## 🤖 Model Types

### Template Model (Default)
- **Best for**: Fixed-layout forms (same vendor invoice, same form type)
- **Training time**: ~1 second
- **GPU required**: No (CPU only)
- **How it works**: Learns spatial anchor positions for each field; during inference, extracts text found in the same relative position

### Neural Model (LayoutLMv3)
- **Best for**: Variable-layout documents (invoices from different vendors)
- **Training time**: 5-30 minutes (faster with GPU)
- **GPU required**: Optional (falls back to CPU)
- **How it works**: Fine-tunes microsoft/layoutlmv3-base using BIO token classification

---

## 📁 Output Format (Azure DI Compatible)

```json
{
  "status": "succeeded",
  "modelType": "template",
  "confidence": 0.94,
  "pages": [...],
  "fields": {
    "invoice_number": {
      "type": "string",
      "valueString": "INV-2024-001",
      "confidence": 0.98,
      "boundingRegions": [{"pageNumber": 1, "polygon": [...]}]
    },
    "line_items": {
      "type": "array",
      "valueArray": [
        {
          "type": "object",
          "valueObject": {
            "description": {"type": "string", "valueString": "Software License", "confidence": 0.97},
            "quantity": {"type": "number", "valueNumber": 1, "confidence": 0.99}
          }
        }
      ]
    }
  }
}
```

---

## ⚙️ Configuration

Edit `.env` to customize:

```env
REVIEW_CONFIDENCE_THRESHOLD=0.85  # Fields below this go to review queue
POSTGRES_PASSWORD=your-secure-password
MINIO_ROOT_PASSWORD=your-minio-password
SECRET_KEY=your-secret-key
```

---

## 🛠️ Development

### Run without Docker (Python venv)

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
# Set up local PostgreSQL and Redis, then:
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

### View Logs

```bash
docker compose logs -f backend
docker compose logs -f celery_worker
docker compose logs -f frontend
```

---

## 📈 Expected Accuracy

| Training Documents | Accuracy |
|-------------------|---------|
| 5 | 70–80% |
| 20–30 | 85–92% |
| 50 | 94–97% |
| 100+ | >97% |

---

## 🗃️ Data Export Formats

- **JSON**: Azure DI-compatible structured output
- **CSV**: Flat key-value pairs; each table becomes a separate section
- **Excel**: Multi-sheet workbook; one sheet per table field + Summary sheet
- **labels.json**: Azure DI-compatible labeling format (for model migration)
