"""Create the two Elasticsearch indices from the JSON mappings in ``index/``. Idempotent."""

from __future__ import annotations

import json
from pathlib import Path

from elasticsearch import Elasticsearch

from app.elastic_client import KNOWLEDGE_INDEX, LOGS_INDEX
from lib.logging import get_logger
from lib.secrets import get_secret

logger = get_logger("opssentinel.mcp-elastic.bootstrap")
_INDEX_DIR = Path(__file__).resolve().parent.parent / "index"
_INDICES = {
    KNOWLEDGE_INDEX: _INDEX_DIR / "opssentinel-knowledge.json",
    LOGS_INDEX: _INDEX_DIR / "opssentinel-logs.json",
}


def ensure_indices(client: Elasticsearch | None = None) -> None:
    client = client or Elasticsearch(
        get_secret("elastic-url"),
        api_key=get_secret("elastic-api-key", default=None) or None,
    )
    for index, mapping_file in _INDICES.items():
        if client.indices.exists(index=index):
            logger.info("index exists", extra={"index": index})
            continue
        body = json.loads(mapping_file.read_text(encoding="utf-8"))
        client.indices.create(index=index, **body)
        logger.info("index created", extra={"index": index})


if __name__ == "__main__":
    ensure_indices()
