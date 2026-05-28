"""Thumbnail generation service — JPEG encoding + decompression-bomb defense."""
import logging

try:
    from PIL import Image
except ImportError:
    Image = None

_logger = logging.getLogger(__name__)

# Defense against decompression bombs. Pillow's default (~89 MP) is reasonable
# but we tighten it for thumbnails.
_MAX_PIXELS = 50_000_000  # ~50 MP


class ThumbnailGenerator:
    """Generate JPEG thumbnails from image blobs."""

    def generate_thumbnail(
        self, file_blob: bytes, max_size_kb: int = 256
    ) -> bytes | None:
        """Generate JPEG thumbnail from image blob.

        Args:
            file_blob: Raw image bytes (JPEG, PNG, etc.)
            max_size_kb: Max output size in KB (default 256)

        Returns:
            JPEG thumbnail bytes, or None on corruption (non-fatal)
        """
        if not file_blob or Image is None:
            return None

        try:
            # Cap decoded pixel count to defend against decompression bombs.
            original_max = Image.MAX_IMAGE_PIXELS
            Image.MAX_IMAGE_PIXELS = _MAX_PIXELS

            io = __import__('io')
            img = Image.open(io.BytesIO(file_blob))
            img.load()  # Force image validation

            # Resize to fit within max_size_kb
            img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)

            output_buf = io.BytesIO()
            # Tune quality to stay under max_size_kb
            for quality in (95, 85, 75, 65, 55, 45):
                output_buf.seek(0)
                output_buf.truncate()
                img.save(output_buf, format='JPEG', quality=quality, optimize=True)
                if output_buf.tell() <= max_size_kb * 1024:
                    break

            return output_buf.getvalue()

        except Exception as e:
            _logger.debug(
                "Thumbnail generation failed (non-fatal): %s", e, exc_info=True
            )
            return None
        finally:
            Image.MAX_IMAGE_PIXELS = original_max
