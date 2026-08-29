from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath, PureWindowsPath

from PIL import Image, UnidentifiedImageError

MAX_BRANDING_UPLOAD_BYTES = 8 * 1_048_576  # 8 MiB upload ceiling
MAX_BRANDING_STORED_BYTES = 1_048_576  # ~1 MiB after optional compression
ALLOWED_BRANDING_CONTENT_TYPES = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/webp",
        "image/gif",
    }
)


@dataclass(frozen=True)
class ProcessedBrandingImage:
    image_data: bytes
    content_type: str
    file_name: str | None
    original_file_name: str | None
    original_byte_size: int
    byte_size: int
    was_compressed: bool


def basenamed_upload_name(filename: str | None) -> str | None:
    if not filename:
        return None
    # strip any path components clients may send
    name = PureWindowsPath(filename).name
    name = PurePosixPath(name).name
    name = name.strip()
    return name or None


def normalize_content_type(raw: str | None, filename: str | None) -> str | None:
    ct = (raw or "").split(";")[0].strip().lower()
    if ct == "image/jpg":
        ct = "image/jpeg"
    if ct in ALLOWED_BRANDING_CONTENT_TYPES:
        return "image/jpeg" if ct == "image/jpg" else ct
    name = (filename or "").lower()
    if name.endswith(".png"):
        return "image/png"
    if name.endswith(".jpg") or name.endswith(".jpeg"):
        return "image/jpeg"
    if name.endswith(".webp"):
        return "image/webp"
    if name.endswith(".gif"):
        return "image/gif"
    return None


def _magic_ok(data: bytes, content_type: str) -> bool:
    if content_type == "image/png" and data[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    if content_type == "image/jpeg" and data[:2] == b"\xff\xd8":
        return True
    if content_type == "image/gif" and data[:6] in (b"GIF87a", b"GIF89a"):
        return True
    if content_type == "image/webp" and data[:4] == b"RIFF" and len(data) >= 12 and data[8:12] == b"WEBP":
        return True
    return False


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGB", "L"):
        return img.convert("RGB") if img.mode == "L" else img
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return img.convert("RGB")


def _encode(img: Image.Image, fmt: str, **save_kwargs) -> bytes:
    buf = BytesIO()
    img.save(buf, format=fmt, **save_kwargs)
    return buf.getvalue()


def _compress_image(img: Image.Image, max_bytes: int) -> tuple[bytes, str]:
    """Reduce dimensions/quality until under max_bytes. Prefer WebP then JPEG."""
    work = img
    # animated GIF / multi-frame: first frame only for branding
    if getattr(work, "n_frames", 1) > 1:
        work.seek(0)
    work = work.copy()
    # strip oversized source: start from reasonable max edge
    max_edge = max(work.size)
    if max_edge > 2048:
        scale = 2048 / max_edge
        work = work.resize(
            (max(1, int(work.width * scale)), max(1, int(work.height * scale))),
            Image.Resampling.LANCZOS,
        )

    rgb = _to_rgb(work)
    has_alpha = work.mode in ("RGBA", "LA") or (work.mode == "P" and "transparency" in work.info)
    candidates: list[tuple[bytes, str]] = []

    if has_alpha:
        rgba = work.convert("RGBA")
        for q in (85, 75, 65, 55, 45, 35):
            data = _encode(rgba, "WEBP", quality=q, method=4)
            candidates.append((data, "image/webp"))
            if len(data) <= max_bytes:
                return data, "image/webp"
    else:
        for q in (88, 80, 70, 60, 50, 40, 30):
            data = _encode(rgb, "WEBP", quality=q, method=4)
            candidates.append((data, "image/webp"))
            if len(data) <= max_bytes:
                return data, "image/webp"
        for q in (88, 80, 70, 60, 50, 40, 30):
            data = _encode(rgb, "JPEG", quality=q, optimize=True, progressive=True)
            candidates.append((data, "image/jpeg"))
            if len(data) <= max_bytes:
                return data, "image/jpeg"

    # progressive downscale
    cur = work
    for _ in range(8):
        w = max(1, int(cur.width * 0.75))
        h = max(1, int(cur.height * 0.75))
        if w == cur.width and h == cur.height:
            break
        cur = cur.resize((w, h), Image.Resampling.LANCZOS)
        if has_alpha:
            data = _encode(cur.convert("RGBA"), "WEBP", quality=40, method=4)
            ct = "image/webp"
        else:
            data = _encode(_to_rgb(cur), "JPEG", quality=40, optimize=True, progressive=True)
            ct = "image/jpeg"
        candidates.append((data, ct))
        if len(data) <= max_bytes:
            return data, ct

    # last resort: smallest candidate even if slightly over (should be rare)
    best = min(candidates, key=lambda x: len(x[0]))
    if len(best[0]) > max_bytes:
        raise ValueError(
            f"Unable to compress image under {max_bytes} bytes (best {len(best[0])} bytes)"
        )
    return best


def process_branding_upload(
    data: bytes,
    *,
    content_type_hint: str | None,
    filename: str | None,
) -> ProcessedBrandingImage:
    original_name = basenamed_upload_name(filename)
    original_size = len(data)
    if original_size == 0:
        raise ValueError("Empty image file")
    if original_size > MAX_BRANDING_UPLOAD_BYTES:
        raise ValueError(
            f"Image exceeds maximum upload size of {MAX_BRANDING_UPLOAD_BYTES} bytes (8 MB)"
        )

    content_type = normalize_content_type(content_type_hint, original_name)
    if content_type is None:
        raise ValueError("Unsupported image type. Use PNG, JPEG, WebP, or GIF.")
    if not _magic_ok(data, content_type):
        raise ValueError("File content does not match a supported image format")

    try:
        with Image.open(BytesIO(data)) as img:
            img.load()
            # keep a working copy after context exit
            loaded = img.copy()
            if getattr(img, "n_frames", 1) > 1:
                loaded.seek(0)
                loaded = loaded.copy()
    except UnidentifiedImageError as exc:
        raise ValueError("File is not a readable image") from exc
    except OSError as exc:
        raise ValueError("File is not a readable image") from exc

    if original_size <= MAX_BRANDING_STORED_BYTES:
        return ProcessedBrandingImage(
            image_data=data,
            content_type=content_type,
            file_name=original_name,
            original_file_name=original_name,
            original_byte_size=original_size,
            byte_size=original_size,
            was_compressed=False,
        )

    stored, stored_ct = _compress_image(loaded, MAX_BRANDING_STORED_BYTES)
    return ProcessedBrandingImage(
        image_data=stored,
        content_type=stored_ct,
        file_name=original_name,
        original_file_name=original_name,
        original_byte_size=original_size,
        byte_size=len(stored),
        was_compressed=True,
    )
