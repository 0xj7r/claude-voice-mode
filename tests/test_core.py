#!/usr/bin/env python3
"""Tests for voice mode core functionality."""

import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))
from tts_player import (
    clean_for_speech,
    extract_last_assistant_message,
    split_sentences,
    send_to_daemon,
    SOCK_PATH,
)


class TestCleanForSpeech(unittest.TestCase):
    """Stripping markdown/code so TTS reads natural text."""

    def test_strips_code_blocks(self):
        text = "Here is code:\n```python\nprint('hi')\n```\nDone."
        assert clean_for_speech(text) == "Here is code:\n\nDone."

    def test_strips_inline_code(self):
        text = "Run `npm install` to start."
        assert clean_for_speech(text) == "Run  to start."

    def test_strips_markdown_links(self):
        text = "See [the docs](https://example.com) for details."
        assert clean_for_speech(text) == "See the docs for details."

    def test_strips_markdown_formatting(self):
        text = "This is **bold** and *italic* and ~~struck~~."
        assert clean_for_speech(text) == "This is bold and italic and struck."

    def test_strips_list_markers(self):
        text = "Items:\n- first\n- second\n+ third"
        assert clean_for_speech(text) == "Items:\nfirst\nsecond\nthird"

    def test_strips_numbered_lists(self):
        text = "Steps:\n1. do this\n2. do that"
        assert clean_for_speech(text) == "Steps:\ndo this\ndo that"

    def test_collapses_excessive_newlines(self):
        text = "A\n\n\n\n\nB"
        assert clean_for_speech(text) == "A\n\nB"

    def test_empty_after_stripping(self):
        text = "```\nonly code\n```"
        assert clean_for_speech(text) == ""

    def test_preserves_plain_text(self):
        text = "Hello, how are you today?"
        assert clean_for_speech(text) == "Hello, how are you today?"

    def test_strips_table_pipes(self):
        text = "| col1 | col2 |\ndata"
        result = clean_for_speech(text)
        assert "|" not in result


class TestSplitSentences(unittest.TestCase):
    """Splitting text into sentence chunks for streaming TTS."""

    def test_splits_on_period(self):
        assert split_sentences("First. Second.") == ["First.", "Second."]

    def test_splits_on_question_mark(self):
        assert split_sentences("What? Really!") == ["What?", "Really!"]

    def test_single_sentence(self):
        assert split_sentences("Just one.") == ["Just one."]

    def test_empty_string(self):
        assert split_sentences("") == []

    def test_no_trailing_punctuation(self):
        result = split_sentences("No punctuation here")
        assert result == ["No punctuation here"]

    def test_filters_empty_chunks(self):
        result = split_sentences("A.  B.")
        assert all(s.strip() for s in result)


class TestExtractLastAssistantMessage(unittest.TestCase):
    """Extracting assistant text from Claude Code transcript files."""

    def _write_jsonl(self, lines: list[dict]) -> str:
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        for line in lines:
            f.write(json.dumps(line) + "\n")
        f.close()
        return f.name

    def _write_json(self, data: list[dict]) -> str:
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(data, f)
        f.close()
        return f.name

    def tearDown(self):
        pass  # temp files cleaned up by OS

    def test_extracts_from_claude_code_jsonl(self):
        """Claude Code format: {"type":"assistant","message":{"role":"assistant","content":[...]}}"""
        path = self._write_jsonl([
            {"type": "user", "message": {"role": "user", "content": "hi"}},
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Hello there!"}],
                },
            },
        ])
        assert extract_last_assistant_message(path) == "Hello there!"

    def test_extracts_from_simple_json_array(self):
        """Simple format: [{"role":"assistant","content":"text"}]"""
        path = self._write_json([
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "Hello!"},
        ])
        assert extract_last_assistant_message(path) == "Hello!"

    def test_skips_tool_use_only_messages(self):
        """Messages with only tool_use blocks have no speakable text."""
        path = self._write_jsonl([
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "tool_use", "id": "x", "name": "Bash", "input": {}}],
                },
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Done."}],
                },
            },
        ])
        # Should get "Done." (the last one with text), not None
        assert extract_last_assistant_message(path) == "Done."

    def test_gets_last_not_first(self):
        path = self._write_jsonl([
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "First"}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Second"}]}},
        ])
        assert extract_last_assistant_message(path) == "Second"

    def test_returns_none_for_nonexistent_file(self):
        assert extract_last_assistant_message("/tmp/nonexistent_12345.jsonl") is None

    def test_returns_none_for_empty_file(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        f.close()
        assert extract_last_assistant_message(f.name) is None

    def test_mixed_text_and_tool_use(self):
        """Assistant message with both text and tool_use blocks; extract only text."""
        path = self._write_jsonl([
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Let me check."},
                        {"type": "tool_use", "id": "x", "name": "Bash", "input": {}},
                    ],
                },
            },
        ])
        assert extract_last_assistant_message(path) == "Let me check."


class TestSocketCommunication(unittest.TestCase):
    """Hook sends text to daemon via Unix socket."""

    def test_send_returns_false_when_no_daemon(self):
        """No socket file means no daemon running."""
        # Ensure socket doesn't exist
        try:
            os.unlink(SOCK_PATH)
        except FileNotFoundError:
            pass
        assert send_to_daemon("test") is False

    def test_send_and_receive_via_socket(self):
        """Text sent by hook arrives at daemon socket."""
        test_sock = SOCK_PATH + ".test"
        received = []

        # Simulate daemon
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            os.unlink(test_sock)
        except FileNotFoundError:
            pass
        server.bind(test_sock)
        server.listen(1)

        def accept():
            conn, _ = server.accept()
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            conn.close()
            received.append(data.decode("utf-8"))

        t = threading.Thread(target=accept, daemon=True)
        t.start()

        # Send
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(test_sock)
        sock.sendall(b"Hello daemon")
        sock.close()

        t.join(timeout=2)
        server.close()
        os.unlink(test_sock)

        assert received == ["Hello daemon"]


if __name__ == "__main__":
    unittest.main()
