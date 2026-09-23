# Contracts Database Plan

## Objective

Create a simple SQLite database for the contracts review web app. The app must accept Word, PDF, Markdown, and plain-text files, preserve the original upload, extract searchable text, and support later reviews against a specific document version.

The browser should communicate with SQLite through the web application's backend/API. It should never connect directly to the database file.

## Core design

Separate the following concepts:

- **Contract**: the legal matter being reviewed.
- **Party**: a person or organisation involved in the contract.
- **Document version**: one uploaded Word, PDF, Markdown, or TXT file.
- **Review**: one review performed against one exact document version.
- **Finding**: an issue identified during a review.
- **Authority**: a statute, case, regulation, or guidance source supporting a finding.

This structure preserves historical uploads and prevents a later upload from changing the meaning of an earlier review.

## Proposed tables

### `contracts`

Stores the main contract record.

| Field | Purpose |
|---|---|
| `id` | Primary key |
| `title` | Human-readable contract name |
| `contract_type` | Employment, sale and purchase, tenancy, or other |
| `status` | Draft, under review, reviewed, signed, expired, or archived |
| `client_role` | Employer, employee, buyer, seller, landlord, tenant, etc. |
| `jurisdiction` | Usually Singapore |
| `governing_law` | Contractual governing law |
| `effective_date` | Contract start date |
| `expiry_date` | Contract end date, if any |
| `signature_date` | Date signed |
| `currency` | SGD, USD, etc. |
| `contract_value` | Optional monetary value |
| `metadata_json` | Type-specific information |
| `notes` | General administrative notes |
| `created_at` | Creation timestamp |
| `updated_at` | Last update timestamp |

### `parties`

Stores people and organisations independently from individual contracts.

| Field | Purpose |
|---|---|
| `id` | Primary key |
| `name` | Legal name |
| `party_type` | Person or organisation |
| `registration_number` | Optional company or identity reference |
| `contact_email` | Optional |
| `notes` | Additional information |

### `contract_parties`

Joins contracts to parties.

| Field | Purpose |
|---|---|
| `contract_id` | References `contracts` |
| `party_id` | References `parties` |
| `role` | Employer, employee, buyer, seller, landlord, tenant, guarantor, etc. |

A join table is preferable to fixed `party_a` and `party_b` fields because a contract may involve multiple parties, guarantors, subsidiaries, or co-buyers.

### `contract_documents`

Stores uploaded original files and their versions.

| Field | Purpose |
|---|---|
| `id` | Primary key |
| `contract_id` | References `contracts` |
| `version_number` | Version 1, 2, 3, etc. |
| `original_filename` | Filename supplied by the user |
| `file_extension` | `.docx`, `.pdf`, `.md`, or `.txt` |
| `mime_type` | Validated MIME type |
| `file_size_bytes` | Original file size |
| `file_hash_sha256` | Detect duplicate uploads |
| `file_content` | Original file stored as a SQLite BLOB |
| `is_current` | Whether this is the current version |
| `uploaded_at` | Upload timestamp |
| `uploaded_by` | User identifier, when authentication exists |
| `extraction_status` | Pending, completed, or failed |
| `extraction_error` | Error details if extraction failed |

Original files should be immutable. A revised contract should create a new document row rather than overwrite the previous file.

### `document_text`

Stores text extracted from uploaded documents.

| Field | Purpose |
|---|---|
| `id` | Primary key |
| `document_id` | References `contract_documents` |
| `extracted_text` | Plain text for searching and review |
| `extraction_method` | Word parser, PDF parser, plain text, or Markdown |
| `extracted_at` | Extraction timestamp |

Keep the original binary file and extracted text separately. The original preserves the source document; extracted text supports searching and AI review.

### `reviews`

Stores each review session.

| Field | Purpose |
|---|---|
| `id` | Primary key |
| `contract_id` | References `contracts` |
| `document_id` | Exact version reviewed |
| `skill_name` | Employment, sale/purchase, tenancy, etc. |
| `review_perspective` | Employer, employee, buyer, seller, landlord, tenant |
| `review_status` | Pending, in progress, completed, or failed |
| `review_date` | Date of review |
| `research_date` | Date legal authorities were checked |
| `recommendation` | Proceed, subject to changes, or resolve blockers |
| `summary` | Overall review summary |
| `created_at` | Creation timestamp |
| `completed_at` | Completion timestamp |

A review must reference the exact document version used for the review.

### `findings`

Stores individual review issues.

| Field | Purpose |
|---|---|
| `id` | Primary key |
| `review_id` | References `reviews` |
| `finding_id` | Human-readable identifier such as `EMP-001` |
| `rank` | Priority order |
| `severity` | Critical, high, medium, or low |
| `confidence` | High, medium, or low |
| `category` | Termination, salary, deposit, title, repairs, etc. |
| `clause_reference` | Clause or page reference |
| `clause_text` | Relevant quotation |
| `risk_description` | Explanation of the risk |
| `trigger_scenario` | What could happen |
| `consequence` | Financial, legal, operational, or career impact |
| `recommendation` | Proposed amendment or action |
| `fallback_position` | Negotiation fallback |
| `residual_risk` | Risk remaining after the proposed fix |
| `status` | Open, accepted, amended, rejected, or resolved |

### `authorities`

Stores legal sources and other supporting sources.

| Field | Purpose |
|---|---|
| `id` | Primary key |
| `authority_type` | Statute, case, regulation, or guidance |
| `title` | Authority title |
| `citation` | Formal citation |
| `url` | Primary-source link |
| `accessed_date` | Date accessed |
| `notes` | Proposition or research notes |

### `finding_authorities`

Joins findings to authorities.

| Field | Purpose |
|---|---|
| `finding_id` | References `findings` |
| `authority_id` | References `authorities` |
| `pinpoint` | Section, subsection, or judgment paragraph |
| `application_notes` | How the authority applies |

## Initial SQLite schema

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE contracts (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    contract_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    client_role TEXT,
    jurisdiction TEXT DEFAULT 'Singapore',
    governing_law TEXT,
    effective_date TEXT,
    expiry_date TEXT,
    signature_date TEXT,
    currency TEXT,
    contract_value NUMERIC,
    metadata_json TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE parties (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    party_type TEXT NOT NULL,
    registration_number TEXT,
    contact_email TEXT,
    notes TEXT
);

CREATE TABLE contract_parties (
    contract_id INTEGER NOT NULL REFERENCES contracts(id),
    party_id INTEGER NOT NULL REFERENCES parties(id),
    role TEXT NOT NULL,
    PRIMARY KEY (contract_id, party_id, role)
);

CREATE TABLE contract_documents (
    id INTEGER PRIMARY KEY,
    contract_id INTEGER NOT NULL REFERENCES contracts(id),
    version_number INTEGER NOT NULL,
    original_filename TEXT NOT NULL,
    file_extension TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    file_hash_sha256 TEXT NOT NULL,
    file_content BLOB NOT NULL,
    is_current INTEGER NOT NULL DEFAULT 1,
    uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    uploaded_by TEXT,
    extraction_status TEXT NOT NULL DEFAULT 'pending',
    extraction_error TEXT,
    UNIQUE(contract_id, version_number),
    UNIQUE(file_hash_sha256)
);

CREATE TABLE document_text (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL UNIQUE REFERENCES contract_documents(id),
    extracted_text TEXT NOT NULL,
    extraction_method TEXT NOT NULL,
    extracted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE reviews (
    id INTEGER PRIMARY KEY,
    contract_id INTEGER NOT NULL REFERENCES contracts(id),
    document_id INTEGER NOT NULL REFERENCES contract_documents(id),
    skill_name TEXT NOT NULL,
    review_perspective TEXT,
    review_status TEXT NOT NULL DEFAULT 'pending',
    review_date TEXT,
    research_date TEXT,
    recommendation TEXT,
    summary TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);

CREATE TABLE findings (
    id INTEGER PRIMARY KEY,
    review_id INTEGER NOT NULL REFERENCES reviews(id),
    finding_id TEXT NOT NULL,
    rank INTEGER,
    severity TEXT NOT NULL,
    confidence TEXT,
    category TEXT,
    clause_reference TEXT,
    clause_text TEXT,
    risk_description TEXT NOT NULL,
    trigger_scenario TEXT,
    consequence TEXT,
    recommendation TEXT,
    fallback_position TEXT,
    residual_risk TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    UNIQUE(review_id, finding_id)
);

CREATE TABLE authorities (
    id INTEGER PRIMARY KEY,
    authority_type TEXT NOT NULL,
    title TEXT NOT NULL,
    citation TEXT,
    url TEXT,
    accessed_date TEXT,
    notes TEXT
);

CREATE TABLE finding_authorities (
    finding_id INTEGER NOT NULL REFERENCES findings(id),
    authority_id INTEGER NOT NULL REFERENCES authorities(id),
    pinpoint TEXT NOT NULL,
    application_notes TEXT,
    PRIMARY KEY (finding_id, authority_id, pinpoint)
);

CREATE INDEX idx_contract_documents_contract
    ON contract_documents(contract_id);

CREATE INDEX idx_reviews_contract
    ON reviews(contract_id);

CREATE INDEX idx_findings_review
    ON findings(review_id);
```

## Type-specific metadata

Employment, tenancy, and sale-and-purchase contracts require different intake information. Avoid adding many specialised columns in the first version. Use `metadata_json` for supplementary information while keeping common, searchable fields as normal columns.

Example:

```json
{
  "employment": {
    "salary": 8000,
    "work_pass_status": "EP",
    "probation_months": 3
  },
  "tenancy": {
    "premises": "123 Example Road",
    "monthly_rent": 5000,
    "deposit": 10000
  }
}
```

## Upload workflow

1. The user selects a Word, PDF, Markdown, or TXT file.
2. The backend validates the extension, MIME type, file size, and file signature where practical.
3. The backend calculates a SHA-256 hash.
4. The backend creates or updates the contract record.
5. The backend stores the original file in `contract_documents` as a BLOB.
6. The backend assigns a new immutable version number and marks it current.
7. The backend extracts text:
   - `.docx`: Word document parser
   - `.pdf`: PDF text extractor
   - `.md` and `.txt`: direct text reading
8. The backend stores extracted text in `document_text`.
9. The user starts a review against that exact document version.

The upload and database insert should be transactional, so an incomplete upload does not leave a misleading contract record.

## Suggested API endpoints

```text
POST   /api/contracts
GET    /api/contracts
GET    /api/contracts/{id}
PATCH  /api/contracts/{id}

POST   /api/contracts/{id}/documents
GET    /api/documents/{id}/download
GET    /api/documents/{id}/text

POST   /api/contracts/{id}/reviews
GET    /api/reviews/{id}
PATCH  /api/findings/{id}
```

## SQLite operating rules

Use the following connection settings:

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
```

Also:

- Store timestamps in UTC.
- Use ISO-8601 timestamp text.
- Use parameterised SQL or an ORM.
- Do not expose the database file through the web server's static-file directory.
- Back up `contracts.db` regularly.
- Add authentication before using the app with confidential contracts.
- Add virus scanning and upload-size limits before accepting untrusted files.

## Implementation phases

### Phase 1: Document intake

- Create the SQLite database and migrations.
- Create contracts, parties, and document-version tables.
- Implement upload for Word, PDF, Markdown, and TXT files.
- Store the original BLOB and extracted text.
- Add contract list, detail, download, and version history views.

### Phase 2: Review preparation

- Add contract type and client perspective.
- Add party management.
- Add type-specific metadata for employment, tenancy, and sale/purchase contracts.
- Add full-text search over extracted contract text.

### Phase 3: Review records

- Add reviews, findings, authorities, and pinpoint citations.
- Display findings in severity order.
- Link every finding to the reviewed document version.
- Add review status and finding-resolution tracking.

### Phase 4: Security and scale

- Add user accounts and permissions.
- Add audit history.
- Consider encrypted external file storage if BLOBs make the database too large.
- Consider PostgreSQL if multiple users or large document volumes make SQLite unsuitable.

## Key architectural decision

For the initial system, store the original uploaded file inside SQLite as a BLOB. Keep the schema independent of the storage mechanism so files can later move to filesystem or object storage without changing the relationships between contracts, document versions, reviews, findings, and authorities.

The most important rule is that every uploaded file is an immutable document version, and every review records the exact version it used.
