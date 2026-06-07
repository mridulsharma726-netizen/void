"""
VOID Media Namespace
===================

Exposes screenshot and audio/image processing functions.
"""

from tools.registry import execute_tool

def take_screenshot():
    return execute_tool("screenshot")
