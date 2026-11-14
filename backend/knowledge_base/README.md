# Knowledge base foundation

The knowledge base stores uploaded document metadata in `KnowledgeDocument`
and future extracted text chunks in `DocumentChunk`. The chunk model reserves
a 384-dimensional pgvector field for the planned
`sentence-transformers/all-MiniLM-L6-v2` embedding model.

Day 2 implements staff-only PDF/TXT upload and text extraction. Day 3 adds
character-based overlapping chunks and transactional chunk replacement. It
does not implement embedding generation, vector search, or LLM generation.
The intended
production vector backend is PostgreSQL with the pgvector extension. When the
project uses the existing SQLite fallback, future retrieval code will use a
NumPy similarity-search adapter instead.

Chunking defaults to a maximum of 2,000 characters with a 200-character
overlap. This is an approximate token equivalent (rather than a tokenizer
count) chosen to avoid an unnecessary tokenizer dependency. The values are
configurable through `RAG_CHUNK_SIZE` and `RAG_CHUNK_OVERLAP`.

Day 4 adds cached local embeddings using
`sentence-transformers/all-MiniLM-L6-v2`. Embeddings are normalized 384-value
vectors, generated in batches (default 32), and stored on each chunk for the
planned pgvector integration. The model is loaded lazily once per process.

Day 5 adds `POST /api/knowledge-base/documents/search/` for staff-only semantic
search. PostgreSQL uses pgvector cosine distance and an HNSW index; SQLite
development uses the NumPy fallback. Configure `RAG_RETRIEVAL_TOP_K` and
`RAG_RETRIEVAL_MIN_SIMILARITY` to control result limits and filtering.

Day 6 adds the staff-only JWT-protected `POST /api/ai/answer/` endpoint. It
reuses the embedding and similarity-search services, bounds the labelled
knowledge-base context with `RAG_CONTEXT_MAX_CHARS`, and delegates grounded
answer generation to the provider named by `RAG_LLM_PROVIDER`. The default
`disabled` provider returns a service-unavailable response when relevant
context exists; questions without relevant context return a safe answer
without calling an LLM.
