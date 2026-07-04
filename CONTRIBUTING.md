# VOID MK1 - Contributing Guidelines

## Logging Conventions

To maintain a robust and observable system, all new code and refactors must adhere to the following logging conventions.

### Exception Handling
**DO NOT** use silent exception swallowing (e.g., `except Exception: pass` or bare `except:`). Silent failures hide critical bugs and make diagnosing issues extremely difficult.

When catching exceptions, especially generic `Exception`, you must log the error with the appropriate context before proceeding or falling back.

**Incorrect (Silent Swallowing):**
```python
try:
    data = fetch_external_data()
except Exception:
    pass
```

**Correct (Structured Logging):**
```python
import logging
logger = logging.getLogger("void.your_module_name")

try:
    data = fetch_external_data()
except Exception as e:
    logger.debug(f"[MODULE NAME] Failed to fetch external data: {e}")
    # Proceed with fallback logic if necessary
```

### Log Levels
- **DEBUG**: Used for minor, non-critical failures in background tasks (e.g., failed to connect to an optional service, temporary network hiccup).
- **INFO**: Used to trace standard application state changes (e.g., "Starting recording loop", "Agent spawned").
- **WARNING**: Used for recoverable but unexpected situations that might impact functionality (e.g., "API key missing, falling back to local model").
- **ERROR**: Used for major system failures that require immediate attention (e.g., "Failed to initialize SQLite database", "Required model file not found").

### Module-Specific Loggers
Always initialize a logger at the top of your module to ensure logs are appropriately tagged:
```python
import logging
logger = logging.getLogger("void.module_name")
```

By following these conventions, we ensure VOID remains stable, diagnosable, and resilient as it scales.
