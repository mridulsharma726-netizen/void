"""
VOID AI Namespace
================

Exposes local habits learning, self-modifier LLM loop, and self-optimization.
"""

from tools.learning_system import learn_preference
from tools.self_modifier import self_repair_workflow
from tools.self_optimizer import auto_repair
