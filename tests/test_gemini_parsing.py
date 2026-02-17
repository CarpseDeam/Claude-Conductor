import unittest
from unittest.mock import MagicMock
import json
import sys
from pathlib import Path

# Add src to path so we can import gui_viewer
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gui_viewer import ClaudeOutputWindow

class TestGeminiParsing(unittest.TestCase):
    def setUp(self):
        # Mock Tkinter to avoid GUI initialization
        self.mock_tk = MagicMock()
        with unittest.mock.patch('gui_viewer.tk', self.mock_tk):
            self.window = ClaudeOutputWindow(
                project_path=".",
                prompt="test",
                cli="gemini"
            )
        # Reset stats
        self.window._stats = self.window._init_stats()

    def test_tool_use_parsing(self):
        # Actual output observed from CLI
        # "dir_path" is used by Gemini's list_directory
        json_line = '{"type":"tool_use","timestamp":"...","tool_name":"list_directory","tool_id":"...","parameters":{"dir_path":"custom_dir"}}'
        
        segments = self.window._format_line_gemini(json_line)
        
        # Check if tool was detected
        self.assertEqual(self.window._stats["tools_used"], 1)
        
        # Check output segments for correct path
        # Should contain "custom_dir"
        text_content = "".join(text for text, tag in segments)
        self.assertIn("custom_dir", text_content)

    def test_tool_result_success(self):
        json_line = '{"type":"tool_result","timestamp":"...","tool_id":"...","status":"success","output":"Listed files..."}'
        segments = self.window._format_line_gemini(json_line)
        
        # Should be success
        self.assertTrue(any("success" in tag for _, tag in segments))
        self.assertFalse(any("error" in tag for _, tag in segments))

    def test_tool_result_error(self):
        json_line = '{"type":"tool_result","timestamp":"...","tool_id":"...","status":"error","output":"Some error","error":{"message":"..."}}'
        segments = self.window._format_line_gemini(json_line)
        
        # Should be error
        self.assertTrue(any("error" in tag for _, tag in segments))
        self.assertEqual(self.window._stats["errors"], 1)

if __name__ == '__main__':
    unittest.main()
