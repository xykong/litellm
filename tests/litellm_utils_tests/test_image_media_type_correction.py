"""
Tests for image media_type mismatch correction.

Anthropic API rejects requests where the declared media_type does not match
the actual image bytes, e.g. 'image/png' header on a JPEG payload:

  "messages.48.content.0.tool_result.content.1.image.source.base64:
   The image was specified using the image/png media type, but the image
   appears to be a image/jpeg image"

Two code paths need the fix:

1. /chat/completions (OpenAI format)
   - convert_to_anthropic_image_obj() in factory.py
   - called when images are in data-URI form: data:image/png;base64,...

2. /v1/messages (Anthropic native format, pass-through)
   - anthropic_messages_handler() in handler.py
   - images are forwarded directly, including nested tool_result content blocks

These tests follow red-green-refactor TDD:
  RED  : tests fail on unpatched code
  GREEN: tests pass after the fix is applied
  (They remain as regression tests / release smoke tests thereafter)
"""

import base64
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath("../../.."))


# ---------------------------------------------------------------------------
# Minimal magic-byte payloads  (real image headers, rest zeroed)
# ---------------------------------------------------------------------------


def _make_jpeg_b64(size: int = 256) -> str:
    """Return base64 of a minimal JPEG magic-byte payload."""
    data = bytearray(size)
    data[0:3] = b"\xff\xd8\xff"  # JPEG SOI + APP0 marker
    return base64.b64encode(bytes(data)).decode()


def _make_png_b64(size: int = 256) -> str:
    """Return base64 of a minimal PNG magic-byte payload."""
    data = bytearray(size)
    data[0:8] = b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"  # full 8-byte PNG signature
    return base64.b64encode(bytes(data)).decode()


def _make_webp_b64(size: int = 256) -> str:
    """Return base64 of a minimal WebP magic-byte payload."""
    data = bytearray(size)
    data[0:4] = b"RIFF"
    data[8:12] = b"WEBP"
    return base64.b64encode(bytes(data)).decode()


# ===========================================================================
# PATH 1 – factory.py  /  convert_to_anthropic_image_obj
# ===========================================================================


class TestConvertToAnthropicImageObjMediaTypeCorrection:
    """
    Tests for convert_to_anthropic_image_obj() in
    litellm/litellm_core_utils/prompt_templates/factory.py

    The function receives a data-URI like:
        data:image/png;base64,<JPEG bytes>

    and must return an object whose media_type matches the ACTUAL bytes,
    not the declared prefix.
    """

    def _call(self, data_uri: str):
        from litellm.litellm_core_utils.prompt_templates.factory import (
            convert_to_anthropic_image_obj,
        )

        return convert_to_anthropic_image_obj(data_uri, format=None)

    def test_correct_media_type_when_jpeg_declared_as_png(self):
        """
        JPEG bytes with 'image/png' declaration → should return 'image/jpeg'.
        This is the exact bug reported by the user (req_011CZz6xv2WrAh591jXehniT).
        """
        jpeg_b64 = _make_jpeg_b64()
        data_uri = f"data:image/png;base64,{jpeg_b64}"

        result = self._call(data_uri)

        assert result["media_type"] == "image/jpeg", (
            f"Expected 'image/jpeg' (detected from magic bytes) but got "
            f"'{result['media_type']}'. The fix in convert_to_anthropic_image_obj() "
            f"is missing – it should detect the real format from the first bytes."
        )

    def test_correct_media_type_when_png_declared_as_jpeg(self):
        """PNG bytes with 'image/jpeg' declaration → should return 'image/png'."""
        png_b64 = _make_png_b64()
        data_uri = f"data:image/jpeg;base64,{png_b64}"

        result = self._call(data_uri)

        assert result["media_type"] == "image/png", f"Expected 'image/png' but got '{result['media_type']}'."

    def test_no_change_when_jpeg_declared_correctly(self):
        """JPEG bytes with correct 'image/jpeg' declaration → should stay 'image/jpeg'."""
        jpeg_b64 = _make_jpeg_b64()
        data_uri = f"data:image/jpeg;base64,{jpeg_b64}"

        result = self._call(data_uri)

        assert result["media_type"] == "image/jpeg"

    def test_no_change_when_png_declared_correctly(self):
        """PNG bytes with correct 'image/png' declaration → should stay 'image/png'."""
        png_b64 = _make_png_b64()
        data_uri = f"data:image/png;base64,{png_b64}"

        result = self._call(data_uri)

        assert result["media_type"] == "image/png"

    def test_fallback_gracefully_when_bytes_unrecognized(self):
        """
        Unknown bytes (all zeros) → should fall back to the declared media_type
        gracefully without raising.
        """
        unknown_b64 = base64.b64encode(bytes(256)).decode()
        data_uri = f"data:image/png;base64,{unknown_b64}"

        result = self._call(data_uri)

        # Must not raise; media_type may be png (declared) or anything else – just not an error
        assert "media_type" in result
        assert result["media_type"] is not None


# ===========================================================================
# PATH 2 – handler.py  /  _fix_image_media_types_in_messages
# ===========================================================================


class TestFixImageMediaTypesInMessages:
    """
    Tests for _fix_image_media_types_in_messages() in
    litellm/llms/anthropic/experimental_pass_through/messages/handler.py

    This function walks Anthropic-native message dicts and corrects any
    image source whose declared media_type mismatches the actual bytes,
    including images nested inside tool_result content blocks.
    """

    def _call(self, messages):
        from litellm.llms.anthropic.experimental_pass_through.messages.handler import (
            _fix_image_media_types_in_messages,
        )

        return _fix_image_media_types_in_messages(messages)

    # --- top-level image blocks ---

    def test_fixes_top_level_image_block_jpeg_declared_as_png(self):
        """
        Direct image block with JPEG bytes but 'image/png' declared → corrected.
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",  # wrong
                            "data": _make_jpeg_b64(),
                        },
                    }
                ],
            }
        ]

        result = self._call(messages)

        source = result[0]["content"][0]["source"]
        assert source["media_type"] == "image/jpeg", (
            f"Expected 'image/jpeg' after correction, got '{source['media_type']}'. "
            f"_fix_image_media_types_in_messages() is missing or incomplete."
        )

    def test_fixes_top_level_image_block_png_declared_as_jpeg(self):
        """PNG bytes declared as 'image/jpeg' → corrected."""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",  # wrong
                            "data": _make_png_b64(),
                        },
                    }
                ],
            }
        ]

        result = self._call(messages)
        source = result[0]["content"][0]["source"]
        assert source["media_type"] == "image/png"

    def test_leaves_correct_declaration_unchanged(self):
        """Correct jpeg+jpeg declaration must NOT be modified."""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": _make_jpeg_b64(),
                        },
                    }
                ],
            }
        ]

        result = self._call(messages)
        source = result[0]["content"][0]["source"]
        assert source["media_type"] == "image/jpeg"

    # --- tool_result nested image blocks (the exact production failure) ---

    def test_fixes_image_inside_tool_result_content(self):
        """
        CRITICAL: This reproduces the exact production failure:
          messages[48].content[0].tool_result.content[1].image.source.base64
          declared image/png but bytes were JPEG.

        The function must descend into tool_result content blocks.
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_abc123",
                        "content": [
                            {
                                "type": "text",
                                "text": "Here is the screenshot",
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",  # WRONG – actually JPEG
                                    "data": _make_jpeg_b64(),
                                },
                            },
                        ],
                    }
                ],
            }
        ]

        result = self._call(messages)

        tool_result = result[0]["content"][0]
        image_block = tool_result["content"][1]
        source = image_block["source"]

        assert source["media_type"] == "image/jpeg", (
            f"Expected 'image/jpeg' inside tool_result, got '{source['media_type']}'. "
            f"_fix_image_media_types_in_messages() must recurse into tool_result content."
        )

    def test_fixes_multiple_images_across_messages(self):
        """Multiple messages, multiple mislabeled images → all corrected."""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",  # wrong
                            "data": _make_jpeg_b64(),
                        },
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_xyz",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",  # wrong
                                    "data": _make_png_b64(),
                                },
                            }
                        ],
                    }
                ],
            },
        ]

        result = self._call(messages)

        assert result[0]["content"][0]["source"]["media_type"] == "image/jpeg"
        assert result[1]["content"][0]["content"][0]["source"]["media_type"] == "image/png"

    def test_ignores_url_type_sources(self):
        """Images with type='url' must be left untouched (no base64 to decode)."""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "url",
                            "url": "https://example.com/image.jpg",
                        },
                    }
                ],
            }
        ]

        result = self._call(messages)
        # Must not raise, source unchanged
        source = result[0]["content"][0]["source"]
        assert source["type"] == "url"
        assert "media_type" not in source or source.get("media_type") is None

    def test_handles_string_content_gracefully(self):
        """Messages with string content (not list) must pass through unchanged."""
        messages = [
            {"role": "user", "content": "Hello, world!"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        result = self._call(messages)

        assert result[0]["content"] == "Hello, world!"
        assert result[1]["content"] == "Hi there!"

    def test_returns_messages_unchanged_when_no_images(self):
        """Pure text messages must come back byte-for-byte identical."""
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": "What is the weather?"}],
            }
        ]

        result = self._call(messages)
        assert result == messages

    def test_does_not_raise_on_corrupted_base64(self):
        """Corrupted / non-base64 data must not propagate an exception."""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": "not-valid-base64!!!",
                        },
                    }
                ],
            }
        ]

        # Must not raise
        result = self._call(messages)
        # media_type stays as declared (fallback behaviour)
        source = result[0]["content"][0]["source"]
        assert source["media_type"] == "image/png"
