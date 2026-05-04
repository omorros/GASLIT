from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from gaslit.adversary.local_api import local_api_base


class LocalApiBaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_api_port = os.environ.get("API_PORT")

    def tearDown(self) -> None:
        if self._old_api_port is None:
            os.environ.pop("API_PORT", None)
        else:
            os.environ["API_PORT"] = self._old_api_port

    def test_local_api_base_defaults_to_documented_api_port(self):
        os.environ.pop("API_PORT", None)

        self.assertEqual(local_api_base(), "http://127.0.0.1:8002")

    def test_local_api_base_honors_api_port_override(self):
        os.environ["API_PORT"] = "9001"

        self.assertEqual(local_api_base(), "http://127.0.0.1:9001")


if __name__ == "__main__":
    unittest.main()
