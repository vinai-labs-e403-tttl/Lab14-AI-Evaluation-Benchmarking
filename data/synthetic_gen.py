import json
import os
import re
from pathlib import Path
from typing import Dict, List

import chromadb
from dotenv import load_dotenv
from openai import OpenAI


ROOT = Path(__file__).resolve().parents[1]
CHROMA_PATH = ROOT / "chroma_db"
OUTPUT_PATH = ROOT / "data" / "golden_set.jsonl"
COLLECTION_NAME = "rag_lab"
DEFAULT_MODEL = "gpt-5-mini"


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def limit_context(text: str, max_chars: int = 200) -> str:
    clean = normalize_text(text)
    return clean[:max_chars]


def build_client() -> OpenAI:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY. Set it in the environment or .env.")
    return OpenAI()


def generate_question_pairs(client: OpenAI, document: str, metadata: Dict) -> List[Dict]:
    section = metadata.get("section") or metadata.get("source") or "tài liệu này"
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You generate evaluation samples for a RAG benchmark. "
                    "Given one document chunk and its metadata, create exactly 2 Vietnamese QA pairs. "
                    "Each answer must be directly grounded in the document, concise, and not invent facts."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Section/context label: {section}\n"
                    f"Metadata: {json.dumps(metadata, ensure_ascii=False)}\n"
                    f"Document:\n{document}\n\n"
                    "Return 2 diverse questions in Vietnamese. "
                    "One should be easier factual retrieval, one should be a more specific detail check. "
                    "Expected answers must be in Vietnamese and supported only by the document."
                ),
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "qa_generation",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "qa_1": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "string"},
                                "expected_answer": {"type": "string"},
                                "difficulty": {
                                    "type": "string",
                                    "enum": ["easy", "medium", "hard"],
                                },
                                "type": {"type": "string"},
                            },
                            "required": [
                                "question",
                                "expected_answer",
                                "difficulty",
                                "type",
                            ],
                            "additionalProperties": False,
                        },
                        "qa_2": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "string"},
                                "expected_answer": {"type": "string"},
                                "difficulty": {
                                    "type": "string",
                                    "enum": ["easy", "medium", "hard"],
                                },
                                "type": {"type": "string"},
                            },
                            "required": [
                                "question",
                                "expected_answer",
                                "difficulty",
                                "type",
                            ],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["qa_1", "qa_2"],
                    "additionalProperties": False,
                },
            }
        },
    )
    payload = json.loads(response.output_text)
    context = limit_context(document)
    rows: List[Dict] = []
    for key in ("qa_1", "qa_2"):
        item = payload[key]
        rows.append(
            {
                "question": item["question"].strip(),
                "expected_answer": item["expected_answer"].strip(),
                "context": context,
                "metadata": {
                    **metadata,
                    "difficulty": item["difficulty"],
                    "type": item["type"],
                },
            }
        )
    return rows


def main() -> None:
    openai_client = build_client()
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = chroma_client.get_collection(COLLECTION_NAME)
    results = collection.get(include=["documents", "metadatas"])

    rows: List[Dict] = []
    for document, metadata in zip(results["documents"], results["metadatas"]):
        if not document:
            continue
        rows.extend(generate_question_pairs(openai_client, document, metadata or {}))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(
        f"Saved {len(rows)} rows from {len(results['ids'])} documents to {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
