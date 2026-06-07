import unittest
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.voice_tts import clean_text_for_speech
from tools.error_interpreter import interpret_error

class TestCommunicationAndClarity(unittest.TestCase):
    def test_markdown_removal(self):
        text = "### Heading\nThis is **bold** text and *italic* text."
        expected = "Heading, This is bold text and italic text."
        self.assertEqual(clean_text_for_speech(text), expected)

    def test_links_removal(self):
        text = "Check the logs in [logs.txt](file:///path/to/logs.txt) or click [here](http://example.com) for details."
        expected = "Check the logs in logs.txt or click here for details."
        self.assertEqual(clean_text_for_speech(text), expected)

    def test_code_blocks_replacement(self):
        text = "Here is the code:\n```python\nprint('hello')\n```\nLet me know if you need changes."
        expected = "Here is the code: Code block displayed on screen. Let me know if you need changes."
        self.assertEqual(clean_text_for_speech(text), expected)

    def test_arrows_replacement(self):
        text = "Lines updated: 10 $\\rightarrow$ 15 (improved -> complete)."
        expected = "Lines updated: 10 to 15 (improved to complete)."
        self.assertEqual(clean_text_for_speech(text), expected)

    def test_emojis_removal(self):
        text = "🔓 Developer Mode Enabled, Sir! ⚠️ Warning: PC is active. 🤖 ready."
        expected = "Developer Mode Enabled, Sir! Warning: PC is active. ready."
        self.assertEqual(clean_text_for_speech(text), expected)

    def test_weird_punctuation_and_lists(self):
        text = "- First item\n- Second item\n\nSome spaces  , and multiple dots ... OK."
        expected = "First item, Second item, Some spaces, and multiple dots. OK."
        self.assertEqual(clean_text_for_speech(text), expected)

    def test_error_interpretation(self):
        err_msg = "Connection refused: 10061"
        res = interpret_error(err_msg)
        self.assertIn("Ollama", res)
        self.assertIn("serve", res)

        err_msg2 = "FileNotFoundError: [Errno 2] No such file or directory: 'temp.txt'"
        res2 = interpret_error(err_msg2)
        self.assertIn("file path", res2.lower())

if __name__ == "__main__":
    unittest.main()
