"""
conftest.py
-----------
Shared pytest fixtures and import stubs for the shell/CI environment.

pyodbc, langchain_groq, and langgraph are only available inside the Docker
container (they require the ODBC Driver 18, Groq SDK, and langgraph
respectively). To allow tests that don't exercise the DB or LLM layer to run
without Docker, we stub all three packages here before any test module imports
them.
"""
import sys
from unittest.mock import MagicMock

# Stub pyodbc so tools that import it can be imported without the ODBC driver.
if "pyodbc" not in sys.modules:
    sys.modules["pyodbc"] = MagicMock()

# Stub langchain_groq (requires Groq SDK and network access).
if "langchain_groq" not in sys.modules:
    sys.modules["langchain_groq"] = MagicMock()

# Stub langgraph — app.agent.graph imports create_react_agent from
# langgraph.prebuilt at module level, which fails outside Docker.
if "langgraph" not in sys.modules:
    sys.modules["langgraph"] = MagicMock()
if "langgraph.prebuilt" not in sys.modules:
    sys.modules["langgraph.prebuilt"] = MagicMock()
if "langgraph.graph" not in sys.modules:
    sys.modules["langgraph.graph"] = MagicMock()
