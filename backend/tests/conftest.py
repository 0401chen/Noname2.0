from __future__ import annotations

import os

# Tests must never call a real model provider, even when the developer has a populated
# repository-level .env file for local smoke testing.
os.environ["APP_ENV"] = "test"
os.environ["LLM_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["API_KEY"] = ""
os.environ["SESSION_STORAGE"] = "memory"
