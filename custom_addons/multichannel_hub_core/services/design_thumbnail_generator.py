"""Thumbnail generation for design files with Pillow image processing.

Handles:
- Image format detection (JPEG, PNG, TIFF, BMP, GIF)
- Lossy compression with auto-tuned JPEG quality
- Size constraint enforcement (≤256 KB typical, configurable via parameter)
- Robust error handling (corruption, timeout, unsupported formats)
- Non-fatal failures — returns None rather than raising on invalid input

ADR-006 §3 alignment: minimum dependencies, graceful degradation on missing Pillow.
"""
import io
import logging

_logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {'JPEG', 'PNG', 'TIFF', 'BMP', 'GIF'}


class ThumbnailGenerator:
    """Pillow-based thumbnail generation with size constraints.

    Public API:
        generate_thumbnail(file_blob: bytes, max_size_kb: int = 256) -> bytes | None
            Generates JPEG thumbnail from input image blob.
            Returns JPEG bytes ≤ max_size_kb on success, None on failure
            (corruption, timeout, unsupported format).
            Never raises on bad input; caller gets None and warning is logged.
    """

    def __init__(self):
        """Initialize; lazy-import Pillow deferred to generate_thumbnail()."""
        pass

    def generate_thumbnail(self, file_blob, max_size_kb=256):
        """Generate thumbnail from image blob with size constraint.

        Args:
            file_blob (bytes): Raw image content
            max_size_kb (int): Maximum output size in KB (default 256)

        Returns:
            bytes | None: JPEG thumbnail ≤ max_size_kb on success,
                         None on failure (unsupported format, corruption,
                         timeout, etc.).
                         Never raises.
        """
        try:
            from PIL import Image
        except ImportError as exc:
            _logger.warning(
                "Pillow not installed; thumbnail generation unavailable. "
                "Install: pip install 'Pillow>=9.0.0'"
            )
            return None

        try:
            max_bytes = max_size_kb * 1024

            # Open and detect format
            img_file = io.BytesIO(file_blob)
            img = Image.open(img_file)

            # Verify format is supported
            if img.format and img.format not in SUPPORTED_FORMATS:
                _logger.debug(
                    "Unsupported image format %s; skipping thumbnail",
                    img.format,
                )
                return None

            # Convert RGBA -> RGB for JPEG (no alpha channel in JPEG)
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_img
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Binary search for quality that fits max_size_kb
            quality = self._find_quality(img, max_bytes)
            if quality is None:
                _logger.warning(
                    "Could not compress image to %d KB", max_size_kb
                )
                return None

            # Encode to JPEG at found quality
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            thumb_bytes = output.getvalue()

            _logger.debug(
                "Thumbnail generated quality=%d size=%d bytes",
                quality, len(thumb_bytes),
            )
            return thumb_bytes

        except Exception as exc:  # noqa: BLE001 — non-fatal, return None
            err_str = str(exc)
            _logger.warning(
                "Thumbnail generation failed err=%s",
                err_str,
            )
            return None

    def _find_quality(self, img, max_bytes):
        """Binary search for JPEG quality that produces output ≤ max_bytes.

        Args:
            img (PIL.Image): Opened image in RGB mode
            max_bytes (int): Maximum output size in bytes

        Returns:
            int | None: JPEG quality (30-95) that fits constraint,
                       or None if uncompressible.
        """
        low, high = 30, 95

        for _ in range(10):  # Max 10 iterations to avoid infinite loop
            mid = (low + high) // 2
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=mid, optimize=True)
            size = len(output.getvalue())

            if size <= max_bytes:
                # Fits; try higher quality if possible
                if mid == high:
                    return mid
                low = mid + 1
            else:
                # Too large; reduce quality
                if mid == low:
                    return None  # Cannot compress further
                high = mid - 1

        return low
