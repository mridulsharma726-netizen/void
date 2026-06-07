import subprocess
import time
from pathlib import Path
from typing import List, Optional

class AgentGitIntegration:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir).resolve()

    def _run_git(self, args: List[str]) -> str:
        """Helper to run a git command and return stdout or empty string on error."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return f"Error running git {' '.join(args)}: {e.stderr.strip()}"
        except Exception as e:
            return f"Git exception: {e}"

    def is_git_repo(self) -> bool:
        """Check if workspace is a git repository."""
        res = self._run_git(["rev-parse", "--is-inside-work-tree"])
        return res == "true"

    def status(self) -> str:
        """Get git status."""
        return self._run_git(["status", "--porcelain"])

    def add(self, paths: List[str]) -> str:
        """Add files to staging."""
        return self._run_git(["add"] + paths)

    def commit(self, message: str) -> str:
        """Commit changes."""
        # Config user email/name if not configured
        user_email = self._run_git(["config", "user.email"])
        if not user_email or "Error" in user_email:
            self._run_git(["config", "user.email", "void-agent@void.ai"])
        user_name = self._run_git(["config", "user.name"])
        if not user_name or "Error" in user_name:
            self._run_git(["config", "user.name", "VOID Autonomous Agent"])
            
        return self._run_git(["commit", "-m", message])

    def checkout(self, branch_name: str) -> str:
        """Checkout a branch."""
        return self._run_git(["checkout", branch_name])

    def create_branch(self, branch_name: str) -> str:
        """Create a new branch."""
        return self._run_git(["checkout", "-b", branch_name])

    def diff(self) -> str:
        """Get git diff."""
        return self._run_git(["diff"])

    def create_backup_branch(self) -> str:
        """
        Creates a backup branch (void-backup-timestamp) before edits.
        Returns the branch name.
        """
        if not self.is_git_repo():
            return "Not a Git repository"
            
        timestamp = int(time.time())
        backup_branch = f"void-backup-{timestamp}"
        
        # Save current branch name
        current_branch = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        
        # Create new backup branch from current state
        res = self._run_git(["checkout", "-b", backup_branch])
        
        # Return to current branch
        self._run_git(["checkout", current_branch])
        
        return backup_branch
