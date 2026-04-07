WORKFLOWS = {
    "study_mode": {
        "name": "Study Mode",
        "steps": [
            {"action": "open_app", "args": {"app": "chrome"}},
            {"action": "wait", "args": {"seconds": 1}},
            {"action": "open_url", "args": {"url": "https://pomofocus.io/"}},
            {"action": "open_url", "args": {"url": "https://www.youtube.com/"}},
        ],
    },
    "dev_mode": {
        "name": "Dev Mode",
        "steps": [
            {"action": "open_app", "args": {"app": "vscode"}},
            {"action": "wait", "args": {"seconds": 1}},
            {"action": "open_app", "args": {"app": "chrome"}},
        ],
    },
}
