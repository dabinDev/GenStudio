from __future__ import annotations

from pathlib import Path
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError


SUPPORTED_IMAGE_FORMATS = {"GIF", "JPEG", "PNG", "WEBP"}


def resolve_managed_path(root: str | Path, candidate: str | Path) -> Path:
    managed_root = Path(root).resolve()
    resolved = (managed_root / Path(candidate)).resolve()
    if not resolved.is_relative_to(managed_root):
        raise ValueError("Path is outside the managed root.")
    return resolved


def create_thumbnail(
    source: str | Path,
    destination: str | Path,
    *,
    max_side: int = 640,
    quality: int = 78,
) -> Path:
    source_path = Path(source)
    destination_path = Path(destination)
    if max_side <= 0:
        raise ValueError("Thumbnail maximum side must be positive.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(source_path) as opened:
                if opened.format not in SUPPORTED_IMAGE_FORMATS:
                    raise ValueError("File is not a supported image.")
                image = ImageOps.exif_transpose(opened)
                image.load()
                image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
                if image.mode not in {"RGB", "RGBA"}:
                    image = image.convert("RGBA" if "transparency" in image.info else "RGB")
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(destination_path, format="WEBP", quality=quality, method=6)
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise ValueError("Image is too large to process safely.") from exc
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("File is not a supported image.") from exc

    return destination_path
