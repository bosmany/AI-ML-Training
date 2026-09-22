# Lab: RAG over a real local vector DB, with a Hugging Face Spaces deploy

Extend Ch35's `RagChatbot` (TF-IDF retrieval over an in-memory Python list) into a system backed by
**real, local infrastructure**: a real `chromadb` collection persisted to disk, and a real (offline, no-API-key)
embedding pipeline. Same retrieve -> ground -> (simulated) generate -> monitor shape Ch35 taught, same
`SIM_THRESHOLD = 0.05` cutoff - the vector math is now a real vector database instead of a Python loop.

Separately, this lab ships a complete Gradio app + `requirements.txt` for Hugging Face Spaces, and the exact
manual steps to push it and get a public URL. **That part has never been deployed from this sandbox** - there is
no Hugging Face account or token here - and nothing in this README claims otherwise.

## Why it matters in a real job

Every "build a RAG chatbot" take-home or production ticket eventually asks the same three questions: where do the
vectors actually live (a real vector DB, not a list you re-scan every request), where did the vectors come from
(a real embedder, with a real quality/cost tradeoff you can explain), and how does a stranger reach it (a real
deploy, with real env vars/secrets, not `localhost`). This lab makes you answer all three for real, at zero cost.

## Prerequisites (course chapters)

- [Chapter 35: RAG Chatbot, Deployed](../../projects/ch35-rag-chatbot-deployed.html) - the retrieve/ground/generate/monitor
  pattern this lab extends
- [Chapter 30: NLP capstone](../../nlp/) (TF-IDF + cosine similarity origin)
- [Chapter 34: Agentic AI System](../../projects/ch34-agentic-ai-system.html) (tool-calling context, if you also build lab 5)

## Two-tier tests - what's graded offline vs. what needs an account

| Tier | Files | Needs | Runs by default? |
| --- | --- | --- | --- |
| **Offline / hermetic (graded)** | `test_embeddings.py`, `test_vectorstore.py`, `test_rag.py`, `test_hosted_embedding.py`, `test_hf_space_app.py` | Nothing. Real `chromadb` writing to `tmp_path`, real `scikit-learn` TF-IDF. No network, no key, no account. | Yes - `pytest` / `LAB_TARGET=solution pytest` |
| **Live** | `test_live_hosted_embedding.py` | A real `EMBEDDING_API_KEY` (any OpenAI-compatible `/embeddings` endpoint) | No - marked `@pytest.mark.live`, excluded by `pytest.ini`'s `addopts = -m "not live"`. Run with `pytest -m live` |
| **Manual, not pytest at all** | `hf_space/app.py` + `hf_space/requirements.txt` | A free Hugging Face account | Never runs here - see "Deploying to Hugging Face Spaces" below |

`LAB_TARGET=solution pytest` is the one command that must fully pass for this lab to be considered done, and it
needs no key, no account, and no network.

## Run it

```bash
cd labs/rag-real-vector-db-deploy
pip install -r requirements.txt          # chromadb, scikit-learn, numpy, requests, pytest
pytest -q                                # starter: fails until you implement it
LAB_TARGET=solution pytest -q            # maintainers / CI: reference solution passes, no key needed
```

Edit only `starter/lab/embeddings.py`, `starter/lab/vectorstore.py`, `starter/lab/rag.py` and
`HostedEmbedder.__init__`/`.embed` in `starter/lab/hosted_embedding.py`. Tests import `from lab import ...` and
pick `starter/` or `solution/` via `LAB_TARGET`, same as every other lab.

## The quality tradeoff, honestly

This lab's offline-graded path uses `sklearn.feature_extraction.text.TfidfVectorizer` (with `stop_words="english"`,
matching Ch35's `remove_stop()` step) as the embedder, because it is the only **local, no-API-key, no-account**
embedding approach that is genuinely practical in this environment:

- This venv has `numpy`, `scikit-learn` and `scipy`, but **no `sentence-transformers` / `torch`**, so a real local
  sentence-embedding model is not installed and this lab does not silently pretend it is.
- `chromadb`'s own *default* embedding function would download a small ONNX MiniLM model from Hugging Face's CDN
  the first time it runs - that needs a network call, which breaks the "hermetic, no network" contract every other
  lab in this repo follows. This lab explicitly disables it (`embedding_function=None` on every collection,
  precomputed embeddings passed to every `add`/`upsert`/`query` call) so the graded tests never depend on the
  network being reachable.
- **TF-IDF is lexical, not semantic.** It scores *word overlap*, weighted by how rare a word is across the corpus.
  "How do I get my money back" will score close to zero against a document that only ever says "refund policy" -
  there is no shared vocabulary for TF-IDF to find, even though a human (or a real embedding model) instantly sees
  the connection. `test_similar_text_scores_higher_than_unrelated_text` in `test_embeddings.py` demonstrates the
  case TF-IDF *does* catch (shared words); `test_live_hosted_embedding.py`'s
  `test_hosted_embedder_captures_semantic_similarity_tfidf_misses` demonstrates the paraphrase case it does not,
  the moment you have a real key to run it with.
- This is still a **completely real** local embedding, not a mock: real vectors, real L2 normalisation, real
  cosine geometry inside a real vector database, real ranking. It is simply a cruder representation than an
  embedding model trained for semantic similarity would give you - and the code says so everywhere it matters
  (`embeddings.py`'s docstring, this section, and `hosted_embedding.py`'s docstring).

### Swapping in a real embedding API

`lab/hosted_embedding.py` ships `HostedEmbedder`, a real client for any OpenAI-compatible `POST /embeddings`
endpoint. It is a **drop-in replacement** for `TfidfEmbedder`:

```python
from lab import RagChatbot, HostedEmbedder

bot = RagChatbot("./chroma-data", embedder=HostedEmbedder())  # needs EMBEDDING_API_KEY
bot.load_documents(docs)
```

- Env var: **`EMBEDDING_API_KEY`**. `HostedEmbedder()` raises `RuntimeError` immediately if it is not set (see
  `test_hosted_embedding.py::test_missing_api_key_raises_immediately`) - it is never silently skipped.
- It defaults to OpenAI's `text-embedding-3-small` at `https://api.openai.com/v1`; pass `base_url=`/`model=` for
  any other OpenAI-compatible provider.
- Exercised for real only by `tests/test_live_hosted_embedding.py` (`@pytest.mark.live`, needs the key):
  `EMBEDDING_API_KEY=sk-... pytest -m live tests/test_live_hosted_embedding.py`. Nobody ran that command in this
  sandbox - there is no key here - so no output from it is claimed as real anywhere in this repo.

## The API

| Class | Method | Behaviour |
| --- | --- | --- |
| `TfidfEmbedder` | `fit(corpus)` | Builds the TF-IDF vocabulary; raises `ValueError` on an empty corpus |
| | `embed(texts)` | Returns an `(len(texts), dim)` array of L2-normalised vectors; raises `RuntimeError` if called before `fit` |
| `ChromaVectorStore` | `upsert(ids, texts, embeddings, metadatas=None)` | Insert/replace documents by id in a real, disk-persisted chromadb collection |
| | `query(query_embedding, top_k=3)` | Real cosine nearest-neighbour search; returns `[]` on an empty store, never errors on `top_k` bigger than the store |
| | `delete(ids)` / `reset()` / `count()` | Remove documents / drop the collection / current size |
| `RagChatbot` | `load_documents(docs)` | Fits the embedder and upserts the whole corpus into the vector store |
| | `retrieve(query, top_k=3)` | Embeds the query, returns ranked `RetrievedDocument`s |
| | `chat(query, top_k=3)` | Retrieves, applies `SIM_THRESHOLD`, builds the prompt, returns `{answer, similarity, grounded, sources, prompt}` |
| | `health_report()` | Request/grounded/ungrounded/error counts and rates, from the same `HealthMonitor` Ch35 used |

## Tasks

1. **`embeddings.TfidfEmbedder.fit` / `.embed`** - fit a real `TfidfVectorizer`, embed text into L2-normalised
   vectors, handle the not-yet-fitted and empty-input edge cases.
2. **`vectorstore.ChromaVectorStore.upsert`** - validate lengths, normalise "no metadata" (chromadb rejects an
   empty `{}`, only a non-empty dict or `None`), call the real collection.
3. **`vectorstore.ChromaVectorStore.query`** - validate `top_k`, handle an empty store, and convert chromadb's
   cosine *distance* back into a similarity score (`similarity = 1.0 - distance`).
4. **`rag.RagChatbot.load_documents`** - wire `Embedder.fit`/`.embed` into `ChromaVectorStore.upsert`.
5. **`rag.RagChatbot.retrieve`** - embed one query, delegate to the store.
6. **`rag.RagChatbot.chat`** - apply `SIM_THRESHOLD`, build the prompt only from grounded context, log every call
   (including the empty-query error case) through `HealthMonitor`.
7. **`hosted_embedding.HostedEmbedder.__init__` / `.embed`** - fail fast with a clear `RuntimeError` when no real
   API key is configured (never silently proceed), then implement the real `POST /embeddings` call and response
   parsing. Only exercised for real by the `@pytest.mark.live` test - see "Swapping in a real embedding API".

## Hints

<details><summary>Why does chromadb reject <code>metadatas=[{}]</code>?</summary>

chromadb's validator treats an empty dict as a mistake ("did you mean to pass metadata or not?") and requires
either a real (non-empty) dict or `None`. Normalise with `meta or None` before calling `upsert`.
</details>

<details><summary>Why <code>embedding_function=None</code> on every collection?</summary>

Without it, chromadb assigns its own default embedding function the first time you add documents without
embeddings - which downloads an ONNX model over the network on first use. Passing embeddings explicitly and
setting `embedding_function=None` means this lab's vector store never needs network access, in tests or anywhere
else.
</details>

<details><summary>chromadb "distance" vs. "similarity"</summary>

With `metadata={"hnsw:space": "cosine"}`, chromadb returns `distance = 1 - cosine_similarity` per hit (ranges
`[0, 2]`). This lab's `SIM_THRESHOLD` and all the tests reason in *similarity*, so `query()` must convert:
`similarity = 1.0 - distance`.
</details>

<details><summary>Why remove English stop words from the TF-IDF vectoriser?</summary>

Ch35's hand-rolled TF-IDF calls `remove_stop(tokenize(...))` before building vectors. Without it, common words
("the", "is", "what") appear in nearly every short document, keep a small nonzero TF-IDF weight, and an
completely unrelated query ends up sharing just enough of them to look falsely "grounded". `TfidfVectorizer(...,
stop_words="english")` reproduces Ch35's behaviour.
</details>

<details><summary>Why does <code>RagChatbot</code> re-fit the embedder every <code>load_documents</code> call?</summary>

TF-IDF's vocabulary depends on the corpus it was fit on - there is no way to add a brand-new document with new
words to an already-fit vectoriser without re-fitting (and therefore re-embedding everything). This lab always
calls `load_documents` once per knowledge base; a production system would re-embed and re-upsert the whole
collection on any corpus change, or use an embedding model (like `HostedEmbedder`) that does not need fitting at
all.
</details>

## Deploying to Hugging Face Spaces (manual - do this yourself, it is not live here)

`hf_space/app.py` is a complete, self-contained Gradio app: the same TF-IDF + chromadb retrieval this lab's
`lab` package implements, wrapped in a small UI, with an example knowledge base baked in. It automatically swaps
to `HostedEmbedder`-style real hosted embeddings if you add an `EMBEDDING_API_KEY` secret - otherwise it runs the
offline TF-IDF path with zero configuration.

There is no Hugging Face account or token in this sandbox, so this has not been pushed or run anywhere. To get a
real public URL:

1. Create a free account at <https://huggingface.co/join> (no card required for a CPU-basic Space).
2. Click **New Space** at <https://huggingface.co/new-space>: pick a name, choose the **Gradio** SDK, **Public**
   visibility, and the free **CPU basic** hardware tier.
3. Clone the new Space's git repo it gives you, copy this lab's `hf_space/app.py`, `hf_space/requirements.txt`
   and `hf_space/README.md` into it (these three files ARE the Space's root - `app.py` is what `app_file: app.py`
   in the README's frontmatter points HF at), then:
   ```bash
   git add app.py requirements.txt README.md
   git commit -m "Deploy RAG vector DB demo"
   git push
   ```
   (Hugging Face also accepts a plain file upload through the Space's "Files" web UI if you would rather not use
   git - either way pushes a new build.)
4. Watch the Space build in its "Logs" tab; once it says "Running", your app is live at
   `https://huggingface.co/spaces/<your-hf-username>/<your-space-name>`.
5. Optional, for real semantic retrieval instead of the offline TF-IDF fallback: in the Space's **Settings >
   Variables and secrets**, add a secret named `EMBEDDING_API_KEY` with a real OpenAI (or compatible) key, then
   restart the Space.

```text
# illustrative - this is what a successful build's log looks like once you push it,
# not something that ran in this sandbox
==== Building on the Hub ====
Fetching Space repository...
Installing requirements.txt: gradio, chromadb, scikit-learn, numpy, requests
Starting app... Running on local URL: http://0.0.0.0:7860
==== Space is Running ====
```

## Stretch goals

- Add a `HashingVectorizer`-based embedder (fixed memory, no `fit` step, streams new documents without
  re-fitting) and compare its retrieval quality against `TfidfEmbedder` on the same queries.
- Add chunking: split long documents into overlapping windows before embedding, and have `chat()` cite the
  specific chunk instead of the whole document.
- Add a re-ranking step: retrieve `top_k=10` with TF-IDF, then re-score just those 10 with `HostedEmbedder` when
  a key is available, and return the best of the re-ranked set.
- Wire `hf_space/app.py`'s knowledge base to load from an uploaded file instead of the hardcoded list.

## How this comes up in interviews

- "Why chromadb over a plain Python list of vectors?" (Real indexing (HNSW), persistence, metadata filtering,
  and it scales past "fits in memory and gets linearly re-scanned every query.")
- "TF-IDF vs. a real embedding model - when would you actually ship TF-IDF?" (Zero cost/latency/dependency,
  works fine when queries share vocabulary with documents (FAQ-style, exact terminology); fails on paraphrases,
  synonyms, and cross-lingual queries, where a trained embedding model is worth the cost.)
- "How do you keep a RAG system from hallucinating on out-of-scope questions?" (A similarity threshold gating
  whether retrieved context is even used, exactly like `SIM_THRESHOLD` here - plus, in a real system, an explicit
  "I don't know" instruction to the LLM and monitoring on how often that path fires.)
- "Walk me through deploying this to production." (Local dev -> containerize or push to a managed host (here,
  HF Spaces) -> secrets for API keys, never hardcoded -> health/monitoring -> the exact five steps above.)

## What this lab does not cover

- **No real semantic embedding model runs offline here.** There is no `sentence-transformers`/`torch` in this
  environment; the offline-graded path is TF-IDF, a real but lexical-only representation - see "The quality
  tradeoff, honestly" above.
- **No real Hugging Face deploy happened in this sandbox.** `hf_space/` is a complete, correct, never-yet-pushed
  artifact; `tests/test_hf_space_app.py` only checks it is syntactically valid and correctly configured, it does
  not deploy or run it.
- **No real hosted-embeddings call happened in this sandbox either.** `HostedEmbedder` is real, working code
  against a real API shape, but `test_live_hosted_embedding.py` is skipped without a real `EMBEDDING_API_KEY` -
  which this sandbox does not have.
- **The vector store is a single local chromadb collection**, not a managed/clustered vector DB - no sharding, no
  replication, no access control; a real production deployment would add all three.
