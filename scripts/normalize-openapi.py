#!/usr/bin/env python3

import json
import sys
from pathlib import Path
from typing import Any


def normalize_binary_uploads(value: Any) -> None:
    if isinstance(value, dict):
        if (
            value.get("type") == "string"
            and value.get("contentMediaType") == "application/octet-stream"
        ):
            normalized = {
                ("format" if key == "contentMediaType" else key): (
                    "binary" if key == "contentMediaType" else child
                )
                for key, child in value.items()
            }
            value.clear()
            value.update(normalized)
        for child in value.values():
            normalize_binary_uploads(child)
    elif isinstance(value, list):
        for child in value:
            normalize_binary_uploads(child)


def main() -> None:
    path = Path(sys.argv[1])
    schema = json.loads(path.read_text())
    normalize_binary_uploads(schema)
    path.write_text(json.dumps(schema))


if __name__ == "__main__":
    main()
