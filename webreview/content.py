"""Static content for the two educational pages (Full Stack Development, Natural Language
Processing). Kept separate from views.py because it's data, not request-handling logic --
and because this is teaching material, it should stay accurate to the actual code: check the
referenced file/function still exists before editing a row here.
"""
from __future__ import annotations

FULL_STACK_LAYERS = [
    {
        "layer": "Frontend",
        "technology": "Django templates, plain CSS, vanilla JavaScript",
        "files": "webreview/templates/webreview/*.html, webreview/static/webreview/report.css",
        "description": (
            "What the browser actually renders: the upload form, the progress page (polls a "
            "JSON endpoint every 2.5 seconds and highlights the current step), and the "
            "finished summary with its PDF download button. No React or Vue: the server "
            "renders full HTML pages, and a small amount of JavaScript updates parts of the "
            "page in place."
        ),
    },
    {
        "layer": "Web framework (backend)",
        "technology": "Django 5.2",
        "files": "webreview/views.py, webreview/urls.py, webreview/forms.py, webconfig/urls.py",
        "description": (
            "The layer a browser request actually hits: routing a URL to a view, validating "
            "the uploaded file, checking the CSRF token, and rendering a template with the "
            "result. This is the part most people mean by 'backend', but it is only one layer "
            "of several here."
        ),
    },
    {
        "layer": "Application / domain logic",
        "technology": "Plain Python, no web framework",
        "files": "contract_reviewer/summarize.py, document_extract.py, prompts.py, schemas.py",
        "description": (
            "The actual contract-summarising logic, written so it does not know Django "
            "exists. summarise.py (the command-line tool) calls the exact same functions the "
            "web app calls. Separating this from the web framework means the logic can be "
            "tested and run without a browser or a server."
        ),
    },
    {
        "layer": "AI / language model",
        "technology": "Anthropic Claude, called through LangChain",
        "files": "contract_reviewer/models.py (invoke_structured), models.yaml",
        "description": (
            "Where natural-language understanding happens: one call to a large language "
            "model, constrained to return a fixed schema (ContractSummary) instead of free "
            "text. See the Natural Language Processing page for the detail."
        ),
    },
    {
        "layer": "Data / persistence",
        "technology": "SQLite, via Django's ORM",
        "files": "webreview/models.py, db.sqlite3, webreview/migrations/",
        "description": (
            "Stores every Contract, ContractDocument and Summary row: what was uploaded, "
            "whether text extraction succeeded, and the finished structured result. The ORM "
            "means the Python code never writes raw SQL."
        ),
    },
    {
        "layer": "Background job processing",
        "technology": "django-q2 (a database-backed task queue)",
        "files": "webreview/tasks.py, Q_CLUSTER setting in webconfig/settings.py",
        "description": (
            "Runs the summarisation outside the request/response cycle. An LLM call can take "
            "longer than a browser will wait on one connection, so the web process hands the "
            "job to a queue table, and a separate worker process (qcluster) picks it up."
        ),
    },
    {
        "layer": "Infrastructure / deployment",
        "technology": "WSGI, environment variables, PythonAnywhere",
        "files": "webconfig/settings.py, webconfig/wsgi.py, .env",
        "description": (
            "Configuration that changes between a laptop and the live site (DEBUG, "
            "ALLOWED_HOSTS, the secret key, API keys) without changing a line of application "
            "code, plus the actual server the app runs on."
        ),
    },
    {
        "layer": "Observability / operations",
        "technology": "Python's logging module",
        "files": "LOGGING setting in webconfig/settings.py, logs/webreview.log, webreview/worker_health.py",
        "description": (
            "Records what the app is doing (uploads received, task stages, failures) to a "
            "rotating log file, so a problem can be diagnosed after the fact instead of only "
            "while watching a terminal."
        ),
    },
]

NLP_STEPS = [
    {
        "step": "Text extraction",
        "what_happens": (
            "The PDF or Word file is converted into plain text: PyMuPDF for a PDF, "
            "python-docx for a Word document."
        ),
        "why_it_matters": (
            "A language model reads text, not a PDF's internal layout. This step exists so "
            "there is something for the model to read at all; it is preprocessing, not "
            "language understanding."
        ),
        "code_reference": "contract_reviewer/document_extract.py: extract_document()",
    },
    {
        "step": "Prompt construction",
        "what_happens": (
            "The extracted text is wrapped into a system/user message pair. The contract "
            "text itself is marked as an untrusted <source_document>, kept separate from the "
            "instructions telling the model what to do with it."
        ),
        "why_it_matters": (
            "This is a defence against prompt injection: a clause written to look like an "
            "instruction (\"ignore all prior instructions and...\") is still just data to the "
            "model, never a command it should follow."
        ),
        "code_reference": "contract_reviewer/prompts.py: build_summary_messages()",
    },
    {
        "step": "Structured extraction by the language model",
        "what_happens": (
            "One call to Claude, constrained to return a fixed schema (ContractSummary: "
            "parties, effective date, payment terms, obligations by party, key dates, and "
            "more) instead of free-form prose."
        ),
        "why_it_matters": (
            "This is where the actual language understanding happens: identifying who owes "
            "what to whom, and by when, from unstructured legal prose, and returning it in a "
            "shape the rest of the program can render without guessing at the format."
        ),
        "code_reference": (
            "contract_reviewer/models.py: invoke_structured(), "
            "contract_reviewer/schemas.py: ContractSummary"
        ),
    },
    {
        "step": "Deterministic fact-check",
        "what_happens": (
            "Every monetary figure, date and duration the model wrote is pulled out with a "
            "regular expression and checked, character for character, against the original "
            "extracted text."
        ),
        "why_it_matters": (
            "A language model can misremember or smooth over a figure. This step catches "
            "that specific, checkable class of error without a second model call, and flags "
            "anything it cannot verify rather than trusting it silently."
        ),
        "code_reference": "contract_reviewer/summarize.py: _fidelity_issues()",
    },
]
