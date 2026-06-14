import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
VOID_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(VOID_ROOT))
sys.path.insert(0, str(VOID_ROOT / "server"))

from backend.providers.router import MultiModelRouter
from backend.providers.ollama_local import OllamaProvider

class TestBrainManager(unittest.TestCase):
    def setUp(self):
        self.router = MultiModelRouter()

    def test_provider_initialization(self):
        """Verify all providers are initialized and accessible."""
        self.assertIsNotNone(self.router.ollama_provider)
        self.assertIsNotNone(self.router.openai_provider)
        self.assertIsNotNone(self.router.gemini_provider)
        self.assertIsNotNone(self.router.anthropic_provider)
        self.assertIsNotNone(self.router.kimi_provider)

    @patch("requests.get")
    def test_model_discovery(self, mock_get):
        """Verify Ollama model tags discovery and capability categorization."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {
                    "name": "qwen2.5-coder:7b",
                    "size": 4700000000,
                    "details": {"family": "qwen2"}
                },
                {
                    "name": "deepseek-r1:8b",
                    "size": 4900000000,
                    "details": {"family": "deepseek"}
                },
                {
                    "name": "llama3.2-vision:latest",
                    "size": 5200000000,
                    "details": {"family": "llama"}
                },
                {
                    "name": "qwen2.5:0.5b",
                    "size": 390000000,
                    "details": {"family": "qwen2"}
                }
            ]
        }
        mock_get.return_value = mock_response

        discovered = self.router.ollama_provider.discover_and_categorize_models()
        self.assertIn("qwen2.5-coder:7b", discovered["Coding"])
        self.assertIn("deepseek-r1:8b", discovered["Reasoning"])
        self.assertIn("llama3.2-vision:latest", discovered["Vision"])
        self.assertIn("qwen2.5:0.5b", discovered["Lightweight"])

    @patch("requests.get")
    def test_intelligent_routing(self, mock_get):
        """Verify AUTO mode correctly selects models and providers based on query category."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "qwen2.5-coder:7b", "size": 4700000000, "details": {"family": "qwen2"}},
                {"name": "deepseek-r1:8b", "size": 4900000000, "details": {"family": "deepseek"}},
                {"name": "llama3.2-vision:latest", "size": 5200000000, "details": {"family": "llama"}},
                {"name": "qwen2.5:0.5b", "size": 390000000, "details": {"family": "qwen2"}}
            ]
        }
        mock_get.return_value = mock_response

        # Set router to AUTO mode
        self.router.config["routing_mode"] = "AUTO"

        # 1. Coding Query
        prov_name, prov, model, reason = self.router.select_provider_and_model("write a python script to parse logs")
        self.assertEqual(prov_name, "Local")
        self.assertEqual(model, "qwen2.5-coder:7b")

        # 2. Reasoning Query
        prov_name, prov, model, reason = self.router.select_provider_and_model("prove that root 2 is irrational")
        self.assertEqual(prov_name, "Local")
        self.assertEqual(model, "deepseek-r1:8b")

        # 3. Vision Query
        prov_name, prov, model, reason = self.router.select_provider_and_model("scan the screen and tell me what is active")
        self.assertEqual(prov_name, "Local")
        self.assertEqual(model, "llama3.2-vision:latest")

        # 4. Quick Query
        prov_name, prov, model, reason = self.router.select_provider_and_model("hi")
        self.assertEqual(prov_name, "Local")
        self.assertEqual(model, "qwen2.5:0.5b")

if __name__ == "__main__":
    unittest.main()
