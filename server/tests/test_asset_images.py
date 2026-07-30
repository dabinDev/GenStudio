from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.asset_images import create_thumbnail, resolve_managed_path


def write_image(path: Path, size: tuple[int, int], image_format: str = "JPEG") -> None:
    Image.new("RGB", size, color=(30, 90, 150)).save(path, format=image_format)


def test_create_thumbnail_outputs_bounded_webp_with_aspect_ratio(tmp_path) -> None:
    source = tmp_path / "large.jpg"
    destination = tmp_path / "thumb.webp"
    write_image(source, (1600, 900))

    result = create_thumbnail(source, destination)

    assert result == destination
    with Image.open(destination) as thumbnail:
        assert thumbnail.format == "WEBP"
        assert thumbnail.size == (640, 360)


def test_create_thumbnail_does_not_enlarge_small_images(tmp_path) -> None:
    source = tmp_path / "small.png"
    destination = tmp_path / "small.webp"
    write_image(source, (320, 200), "PNG")

    create_thumbnail(source, destination)

    with Image.open(destination) as thumbnail:
        assert thumbnail.size == (320, 200)


def test_create_thumbnail_rejects_non_images(tmp_path) -> None:
    source = tmp_path / "payload.txt"
    source.write_text("not an image", encoding="utf-8")

    with pytest.raises(ValueError, match="supported image"):
        create_thumbnail(source, tmp_path / "payload.webp")


def test_create_thumbnail_rejects_decompression_bomb_warnings(tmp_path, monkeypatch) -> None:
    source = tmp_path / "suspicious.png"
    write_image(source, (10, 10), "PNG")
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 60)

    with pytest.raises(ValueError, match="too large"):
        create_thumbnail(source, tmp_path / "suspicious.webp")


@pytest.mark.parametrize("candidate", ["../secret", "nested/../../secret", "C:/Windows/System32/config"])
def test_resolve_managed_path_rejects_paths_outside_root(tmp_path, candidate) -> None:
    with pytest.raises(ValueError, match="managed root"):
        resolve_managed_path(tmp_path, candidate)


def test_resolve_managed_path_accepts_a_child_path(tmp_path) -> None:
    assert resolve_managed_path(tmp_path, "nested/image.png") == (tmp_path / "nested" / "image.png").resolve()
