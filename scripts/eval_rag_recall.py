#!/usr/bin/env python3
"""
eval_rag_recall.py — Evaluate Recall@3 for the HealthCore RAG pipeline.

Runs all 8 queries from test-queries.json, checks if the expected source
document appears in the top-3 retrieved chunks, and prints a results table.

Usage:
    cd /workspaces/elige-tu-empresa-wendy-sanchez
    uv run python scripts/eval_rag_recall.py
"""

import json
import sys
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from data.pipelines.rag import retrieve


def evaluate_recall(k: int = 3, min_score: float = 0.3) -> dict:
    """Run all test queries and evaluate Recall@k."""
    queries_path = _PROJECT_ROOT / "data" / "eval" / "test-queries.json"
    with open(queries_path, encoding="utf-8") as f:
        queries = json.load(f)

    results = []
    hits = 0
    total = len(queries)

    print(f"\n{'='*70}")
    print(f"📊 EVALUACIÓN DE RECUPERACIÓN — Recall@{k}")
    print(f"Umbral de similitud: min_score={min_score}")
    print(f"{'='*70}\n")

    for q in queries:
        qid = q["id"]
        question = q["question"]
        expected_doc = q["expected_source_document"]

        # Retrieve top-k chunks
        chunks = retrieve(question, k=k, min_score=min_score)

        retrieved_docs = [c.get("source_document", "?") for c in chunks]
        retrieved_scores = [c.get("_score", 0.0) for c in chunks]
        retrieved_texts = [c.get("text", "")[:80] for c in chunks]

        # Check if expected doc is in retrieved docs
        in_top_k = expected_doc in retrieved_docs

        if in_top_k:
            hits += 1
            verdict = "✅"
        else:
            verdict = "❌"

        # Print result row
        print(f"  {qid} {verdict}")
        print(f"      Pregunta: {question[:90]}...")
        print(f"      Esperado: {expected_doc}")
        print(f"      Top-{k}:   {retrieved_docs}")
        print(f"      Scores:   {[round(s, 4) for s in retrieved_scores]}")

        # Show which position had the match
        if in_top_k:
            pos = retrieved_docs.index(expected_doc) + 1
            print(f"      ✅ Encontrado en posición #{pos} (score: {retrieved_scores[pos-1]:.4f})")
        else:
            # Show what was retrieved instead
            if chunks:
                print(f"      Se recuperó: {retrieved_docs[0]} (score: {retrieved_scores[0]:.4f})")
                print(f"      Fragmento:   {retrieved_texts[0][:100]}...")
            else:
                print(f"      ⚠️  No se recuperaron fragmentos (todos por debajo de {min_score})")
        print()

    # Summary
    recall_pct = (hits / total) * 100
    print(f"{'='*70}")
    print(f"\n📊  RESUMEN: Recall@{k} = {hits}/{total} = {recall_pct:.1f}%")
    print(f"   Objetivo: ≥ 80% {'✅ APROBADO' if recall_pct >= 80 else '❌ NO APROBADO'}")
    print(f"\n{'='*70}\n")

    return {
        "total": total,
        "hits": hits,
        "recall_pct": recall_pct,
        "passed": recall_pct >= 80,
        "results": results,
    }


def run_end_to_end_queries() -> None:
    """Run the full query pipeline for all 8 queries to show answers."""
    from data.pipelines.rag import query

    queries_path = _PROJECT_ROOT / "data" / "eval" / "test-queries.json"
    with open(queries_path, encoding="utf-8") as f:
        queries = json.load(f)

    print(f"\n{'='*70}")
    print(f"💬 RESPUESTAS COMPLETAS (query() con k=5, min_score=0.3)")
    print(f"{'='*70}\n")

    for q in queries:
        qid = q["id"]
        question = q["question"]
        expected_doc = q["expected_source_document"]

        answer = query(question, k=5, min_score=0.3)
        print(f"  [{qid}] {expected_doc}")
        print(f"  Q: {question[:90]}...")
        print(f"  A: {answer[:200]}...")
        print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate RAG Recall@k")
    parser.add_argument("--k", type=int, default=3, help="k for Recall@k (default: 3)")
    parser.add_argument("--min-score", type=float, default=0.3, help="min_score threshold (default: 0.3)")
    parser.add_argument("--answers", action="store_true", help="Also run full query() for each question")
    args = parser.parse_args()

    result = evaluate_recall(k=args.k, min_score=args.min_score)

    if args.answers:
        run_end_to_end_queries()

    sys.exit(0 if result["passed"] else 1)