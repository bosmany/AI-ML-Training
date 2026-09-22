---
title: RAG Real Vector DB Demo
emoji: 📚
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
---

# RAG over a real local vector DB

Small Gradio demo: a fixed "Acme Widgets API" support knowledge base, indexed into a
real chromadb collection with real TF-IDF vectors (or real hosted embeddings if you add
an `EMBEDDING_API_KEY` secret to this Space), queried with real cosine similarity.

This is the deploy target for `labs/rag-real-vector-db-deploy` in the AI-ML-Training
repo - see that lab's README for the full write-up, including exactly how this was
pushed here and the offline/hermetic tests that grade the underlying `lab` package.
