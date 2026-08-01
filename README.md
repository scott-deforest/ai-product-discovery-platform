# AI Product Discovery Platform

A local assessment application that turns product, process, and workflow
documentation into searchable evidence for identifying valuable AI opportunities.

## Sprint 1 status

Sprint 1 establishes the document-ingestion and retrieval foundation:

- Create named assessments with business context.
- Upload PDF, TXT, Markdown, and DOCX files to a specific assessment.
- Extract and preview source text before further processing.
- Split text into ordered, overlapping chunks.
- Create OpenAI embeddings and store them locally in Chroma.
- Retrieve relevant evidence with assessment-level filtering.

The application deliberately exposes each processing stage. A user can verify the
source text and chunks before any later AI assessment or recommendation is added.

## Architecture

```text
Streamlit interface
       |
       +-- SQLite -------- assessments, documents, extractions, chunks
       |
       +-- Local files --- uploads and extracted text
       |
       +-- OpenAI API ---- text embeddings
       |
       +-- Chroma -------- local vector storage and similarity search
```

One Chroma collection stores all document chunks. Each vector carries
`assessment_id`, `document_id`, filename, and chunk index metadata. Retrieval is
filtered by `assessment_id`, preventing evidence from unrelated assessments from
appearing in results.

## Local setup

Python 3.9 or newer is required.

```bash
git clone <repository-url>
cd ai-product-discovery-platform
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Add an OpenAI API key to `.env`:

```text
OPENAI_API_KEY=your_key_here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Never commit `.env` or share an API key.

## Run the application

```bash
python -m streamlit run app.py
```

Open `http://localhost:8501` if the browser does not open automatically.

## Demo workflow

1. Create an assessment named **Customer Support Workflow**.
2. Upload `data/sample_docs/customer_support_workflow.md`.
3. Extract and inspect the document text.
4. Create and inspect the text chunks.
5. Index the chunks with OpenAI embeddings.
6. Search for `What problems slow down customer support?`.
7. Review the retrieved source chunks and their similarity scores.

A similarity score measures vector closeness; it is not a confidence or accuracy
percentage.

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests cover assessment persistence, document storage, text extraction,
overlapping chunk creation, Chroma indexing, and assessment-scoped retrieval.
Vector-store tests use a deterministic fake embedding client and do not call the
OpenAI API.

## Project structure

```text
app.py                         Streamlit interface
src/config.py                  Local paths and configuration
src/database.py                SQLite persistence
src/ingestion.py               Upload storage and text extraction
src/chunking.py                Deterministic overlapping chunks
src/vector_store.py            Embeddings, Chroma, and retrieval
data/sample_docs/              Safe demo documents
tests/                         Automated tests
```

## Data handling

- Uploaded files, extracted text, SQLite data, vectors, and API keys are excluded
  from Git.
- Uploaded files and Chroma vectors remain on the local machine.
- Chunk text and search queries are sent to the OpenAI API to create embeddings.
- The current MVP does not include OCR for scanned PDFs.

## Next milestone

Sprint 2 will build an evidence-grounded assessment workflow on top of retrieved
chunks, while keeping source traceability and human review central to the product.
