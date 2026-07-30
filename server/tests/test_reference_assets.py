from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.reference_assets import (
    collect_reference_image_assets,
    indexed_reference_metadata,
    validate_reference_limit,
)


def test_validate_reference_limit_accepts_ten_unique_urls() -> None:
    references = [{"url": f"https://cdn.test/{index}.png"} for index in range(10)]

    assert validate_reference_limit({"images": references}) == 10


def test_validate_reference_limit_rejects_eleven_unique_urls() -> None:
    references = [f"https://cdn.test/{index}.png" for index in range(11)]

    with pytest.raises(HTTPException) as exc_info:
        validate_reference_limit({"images": references})

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == {"message": "参考图片最多支持 10 张。"}


def test_reference_limit_counts_duplicate_urls_once() -> None:
    references = ["https://cdn.test/same.png"] * 11

    assert validate_reference_limit({"images": references}) == 1


def test_collector_preserves_fixed_frame_roles() -> None:
    references = collect_reference_image_assets(
        {
            "first_frame": "https://cdn.test/first.png",
            "last_frame": "https://cdn.test/last.png",
        }
    )

    assert [reference["role"] for reference in references] == ["first_frame", "last_frame"]


def test_reference_metadata_indexes_from_one() -> None:
    assert indexed_reference_metadata(0, "reference", "参考图") == {
        "role": "reference",
        "label": "参考图",
        "source": "input",
        "index": 1,
    }
