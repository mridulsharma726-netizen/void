import sys
import unittest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
VOID_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(VOID_ROOT))

from tools.agent_network import (
    spawn_agent_network,
    ask_agent,
    initiate_swarm_vote,
    get_network_status,
    SWARM,
    DB_FILE
)

class TestAgentSwarm(unittest.TestCase):
    def setUp(self):
        # We can run async tests inside our setup/test methods
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_swarm_spawning(self):
        """Verify that spawning the swarm registers 10 specialist agents."""
        res = self.loop.run_until_complete(spawn_agent_network())
        self.assertEqual(res["status"], "ok")
        self.assertEqual(len(SWARM), 10)
        self.assertIn("ceo", SWARM)
        self.assertIn("frontend", SWARM)
        self.assertIn("backend", SWARM)
        self.assertIn("debug", SWARM)
        self.assertIn("qa", SWARM)
        self.assertIn("memory", SWARM)

    def test_ask_specific_agent(self):
        """Verify calling a specific agent executes its corresponding task."""
        # Warmup
        self.loop.run_until_complete(spawn_agent_network())
        
        # Test Research Agent
        res = self.loop.run_until_complete(ask_agent("research", "find test_agent_swarm.py"))
        self.assertEqual(res["status"], "ok")
        self.assertIn("Research Agent", res["message"])

    @patch("tools.agent_network.run_agent_llm")
    def test_ceo_handoff_delegation(self, mock_llm):
        """Verify CEO agent chains handoffs based on task keywords."""
        mock_llm.return_value = "👑 [CEO] CEO analysis complete."
        self.loop.run_until_complete(spawn_agent_network())
        
        # Call CEO with a planning instruction -> should trigger a handoff to planner
        res = self.loop.run_until_complete(ask_agent("ceo", "Create a project plan for the database migration"))
        self.assertEqual(res["status"], "ok")
        # Verify the handoff chain message is present in the synthesized output
        self.assertIn("delegating to Planner Agent", res["message"])

    def test_consensus_voting(self):
        """Verify collaborative voting matches consensus rules."""
        res = self.loop.run_until_complete(initiate_swarm_vote("prop_1", "Add security validation to routes"))
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["data"]["outcome"], "APPROVED")

        # Force key should trigger security agent rejection
        res_force = self.loop.run_until_complete(initiate_swarm_vote("prop_2", "Force delete all files in directory"))
        self.assertEqual(res_force["status"], "ok")
        # Since security rejects force operations, it should still approve if majority approves (5 total agents, 4 approve, 1 rejects -> consensus APPROVED)
        # Wait, let's verify if security rejected
        votes = res_force["data"]["votes"]
        self.assertEqual(votes["security"]["vote"], "REJECT")

if __name__ == "__main__":
    unittest.main()
