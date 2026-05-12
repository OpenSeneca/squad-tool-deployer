#!/usr/bin/env python3
"""
Squad Tool Deployer - Manage and deploy tools across all squad agents

This tool helps with:
- Deploying tools to all squad agents
- Checking which tools are installed on which agents
- Keeping tools in sync across agents
- Running validation on all agents
- Rolling out updates

Usage:
    python3 main.py --list-agents
    python3 main.py --deploy squad-config-validator --all-agents
    python3 main.py --check-tool squad-config-validator --all-agents
    python3 main.py --sync-tools --all-agents
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path
import json
import re
from typing import List, Dict, Optional, Tuple

# Base workspace directory
WORKSPACE_DIR = Path.home() / ".openclaw" / "workspace" / "tools"

# Squad agent configuration
SQUAD_AGENTS = {
    "seneca": {
        "host": "100.101.15.68",
        "user": "exedev",
        "role": "Squad Leader"
    },
    "marcus": {
        "host": "100.98.223.103",
        "user": "exedev",
        "role": "Research - AI/ML"
    },
    "galen": {
        "host": "100.123.121.125",
        "user": "exedev",
        "role": "Research - Biopharma"
    },
    "archimedes": {
        "host": "100.100.56.102",
        "user": "exedev",
        "role": "Engineering (local)"
    },
    "argus": {
        "host": "100.108.219.91",
        "user": "exedev",
        "role": "Monitoring"
    },
    "clutch": {
        "host": "100.93.69.117",
        "user": "exedev",
        "role": "Operations"
    },
}

# Core tools that should be installed on all agents
CORE_TOOLS = [
    "squad-config-validator",
    "squad-config-monitor",
    "auto-ingester",
]


class SquadToolDeployer:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.workspace_dir = WORKSPACE_DIR

    def log(self, message: str):
        """Print log message if verbose."""
        if self.verbose:
            print(f"[INFO] {message}", file=sys.stderr)

    def run_ssh_command(self, agent: str, command: List[str], timeout: int = 30) -> Tuple[int, str, str]:
        """Run a command on a remote agent via SSH."""
        agent_config = SQUAD_AGENTS.get(agent)
        if not agent_config:
            return 1, "", f"Unknown agent: {agent}"

        # For local agent, run directly
        if agent == "archimedes":
            self.log(f"Running local: {' '.join(command)}")
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                return result.returncode, result.stdout, result.stderr
            except subprocess.TimeoutExpired:
                return 1, "", f"Command timed out after {timeout}s"

        # For remote agents, use SSH
        ssh_cmd = [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10",
            "-o", "StrictHostKeyChecking=no",
            f"{agent_config['user']}@{agent_config['host']}",
            " ".join(command)
        ]

        self.log(f"Running SSH on {agent}: {' '.join(command)}")

        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", f"SSH connection timed out after {timeout}s"

    def list_agents(self) -> List[Dict[str, str]]:
        """List all squad agents with their status."""
        agents = []
        for agent_name, agent_config in SQUAD_AGENTS.items():
            # Check if agent is reachable
            code, stdout, stderr = self.run_ssh_command(agent_name, ["echo", "OK"], timeout=10)

            agent_info = {
                "name": agent_name,
                "host": agent_config["host"],
                "role": agent_config["role"],
                "status": "UP" if code == 0 and stdout.strip() == "OK" else "DOWN"
            }

            if code != 0:
                agent_info["error"] = stderr.strip() or stdout.strip()

            agents.append(agent_info)

        return agents

    def check_tool_installed(self, agent: str, tool_name: str) -> Dict[str, any]:
        """Check if a tool is installed on an agent."""
        # Check if tool directory exists
        cmd = ["ls", "-d", str(self.workspace_dir / tool_name)]
        code, stdout, stderr = self.run_ssh_command(agent, cmd)

        tool_dir_exists = code == 0

        # Check if tool has setup.py
        setup_exists = False
        version = None

        if tool_dir_exists:
            setup_cmd = ["test", "-f", str(self.workspace_dir / tool_name / "setup.py")]
            setup_code, _, _ = self.run_ssh_command(agent, setup_cmd)
            setup_exists = setup_code == 0

            # Try to get version
            if setup_exists:
                version_cmd = ["grep", "-oP", '(?<=version=")[^"]+',
                              str(self.workspace_dir / tool_name / "setup.py")]
                v_code, v_stdout, _ = self.run_ssh_command(agent, version_cmd)
                if v_code == 0:
                    version = v_stdout.strip()

        return {
            "agent": agent,
            "tool": tool_name,
            "installed": tool_dir_exists,
            "has_setup": setup_exists,
            "version": version
        }

    def deploy_tool(self, agent: str, tool_name: str, source_path: Optional[Path] = None) -> bool:
        """Deploy a tool to an agent."""
        # Find tool source
        if source_path is None:
            source_path = self.workspace_dir / tool_name

        if not source_path.exists():
            print(f"Error: Tool source not found at {source_path}", file=sys.stderr)
            return False

        # Create target directory on agent
        target_dir = self.workspace_dir / tool_name

        print(f"Deploying {tool_name} to {agent}...")

        # Create target directory
        mkdir_cmd = ["mkdir", "-p", str(target_dir)]
        code, _, stderr = self.run_ssh_command(agent, mkdir_cmd)
        if code != 0:
            print(f"Error creating directory: {stderr}", file=sys.stderr)
            return False

        # Use rsync to copy files (for remote) or cp (for local)
        if agent == "archimedes":
            # Local copy - just verify it's already there
            if source_path == target_dir:
                print(f"✓ {tool_name} is already at target location")
                return True

            # Copy files
            cp_cmd = ["cp", "-r", f"{source_path}/.", str(target_dir)]
            code, _, stderr = self.run_ssh_command(agent, cp_cmd)
            if code != 0:
                print(f"Error copying files: {stderr}", file=sys.stderr)
                return False
        else:
            # Remote copy using rsync
            agent_config = SQUAD_AGENTS[agent]
            rsync_cmd = [
                "rsync", "-avz", "--delete",
                "-e", "ssh -o BatchMode=yes -o StrictHostKeyChecking=no",
                f"{source_path}/",
                f"{agent_config['user']}@{agent_config['host']}:{target_dir}/"
            ]

            self.log(f"Running: {' '.join(rsync_cmd)}")

            try:
                result = subprocess.run(
                    rsync_cmd,
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                if result.returncode != 0:
                    print(f"Error copying files: {result.stderr}", file=sys.stderr)
                    return False
            except subprocess.TimeoutExpired:
                print(f"Error: rsync timed out", file=sys.stderr)
                return False

        print(f"✓ Successfully deployed {tool_name} to {agent}")
        return True

    def sync_core_tools(self, agents: List[str]) -> Dict[str, List[str]]:
        """Sync core tools to specified agents."""
        results = {
            "success": [],
            "failed": []
        }

        for tool_name in CORE_TOOLS:
            tool_path = self.workspace_dir / tool_name

            if not tool_path.exists():
                print(f"Warning: Tool {tool_name} not found locally, skipping", file=sys.stderr)
                continue

            for agent in agents:
                if self.deploy_tool(agent, tool_name):
                    results["success"].append(f"{agent}:{tool_name}")
                else:
                    results["failed"].append(f"{agent}:{tool_name}")

        return results

    def run_validation(self, agents: List[str]) -> Dict[str, any]:
        """Run squad-config-validator on specified agents."""
        results = {}

        for agent in agents:
            validator_path = self.workspace_dir / "squad-config-validator" / "main.py"

            if agent == "archimedes":
                # Run locally
                cmd = [sys.executable, str(validator_path), "--local", "--output", "json"]
            else:
                # Run remotely
                cmd = [sys.executable, str(validator_path), "--local", "--output", "json"]

            code, stdout, stderr = self.run_ssh_command(agent, cmd, timeout=60)

            results[agent] = {
                "success": code == 0,
                "output": stdout,
                "error": stderr if code != 0 else None
            }

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Squad Tool Deployer - Manage tools across squad agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all agents and their status
  python3 main.py --list-agents

  # Check if a tool is installed on an agent
  python3 main.py --check-tool squad-config-validator --agent seneca

  # Deploy a tool to an agent
  python3 main.py --deploy squad-config-validator --agent seneca

  # Deploy to all agents
  python3 main.py --deploy squad-config-validator --all-agents

  # Sync all core tools to all agents
  python3 main.py --sync-tools --all-agents

  # Run validation on all agents
  python3 main.py --validate --all-agents

  # Show what tools are installed where
  python3 main.py --inventory
        """
    )

    parser.add_argument(
        "--list-agents",
        action="store_true",
        help="List all squad agents with their status"
    )

    parser.add_argument(
        "--agent", "-a",
        help="Target agent (one of: seneca, marcus, galen, archimedes, argus, clutch)"
    )

    parser.add_argument(
        "--all-agents",
        action="store_true",
        help="Target all agents"
    )

    parser.add_argument(
        "--check-tool", "-c",
        help="Check if a tool is installed on target agent(s)"
    )

    parser.add_argument(
        "--deploy", "-d",
        help="Deploy a tool to target agent(s)"
    )

    parser.add_argument(
        "--sync-tools",
        action="store_true",
        help="Sync all core tools to target agent(s)"
    )

    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run squad-config-validator on target agent(s)"
    )

    parser.add_argument(
        "--inventory",
        action="store_true",
        help="Show tool inventory across all agents"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    deployer = SquadToolDeployer(verbose=args.verbose)

    # List agents
    if args.list_agents:
        agents = deployer.list_agents()
        print("\n" + "=" * 80)
        print("Squad Agents Status")
        print("=" * 80)

        for agent in agents:
            status_symbol = "✅" if agent["status"] == "UP" else "❌"
            print(f"\n{status_symbol} {agent['name']}")
            print(f"   Role: {agent['role']}")
            print(f"   Host: {agent['host']}")
            print(f"   Status: {agent['status']}")
            if "error" in agent:
                print(f"   Error: {agent['error']}")

        print("\n" + "=" * 80)
        return 0

    # Get target agents
    target_agents = []
    if args.all_agents:
        target_agents = list(SQUAD_AGENTS.keys())
    elif args.agent:
        if args.agent not in SQUAD_AGENTS:
            print(f"Error: Unknown agent {args.agent}", file=sys.stderr)
            print(f"Valid agents: {', '.join(SQUAD_AGENTS.keys())}", file=sys.stderr)
            return 1
        target_agents = [args.agent]
    else:
        print("Error: Specify --agent or --all-agents", file=sys.stderr)
        return 1

    # Check tool
    if args.check_tool:
        print(f"\nChecking {args.check_tool} on {len(target_agents)} agent(s)...\n")

        for agent in target_agents:
            result = deployer.check_tool_installed(agent, args.check_tool)
            status = "✅ Installed" if result["installed"] else "❌ Not installed"

            print(f"{agent}:")
            print(f"  Status: {status}")
            if result["installed"]:
                if result["has_setup"]:
                    print(f"  Setup: ✅ Has setup.py")
                    if result["version"]:
                        print(f"  Version: {result['version']}")
                else:
                    print(f"  Setup: ⚠️  No setup.py")

        return 0

    # Deploy tool
    if args.deploy:
        print(f"\nDeploying {args.deploy} to {len(target_agents)} agent(s)...\n")

        success_count = 0
        for agent in target_agents:
            if deployer.deploy_tool(agent, args.deploy):
                success_count += 1

        print(f"\nDeployment complete: {success_count}/{len(target_agents)} agents successful")
        return 0 if success_count == len(target_agents) else 1

    # Sync core tools
    if args.sync_tools:
        print(f"\nSyncing core tools to {len(target_agents)} agent(s)...\n")
        print(f"Core tools: {', '.join(CORE_TOOLS)}\n")

        results = deployer.sync_core_tools(target_agents)

        print(f"\nSync complete:")
        print(f"  Success: {len(results['success'])}")
        print(f"  Failed: {len(results['failed'])}")

        if results['failed']:
            print(f"\nFailed deployments:")
            for item in results['failed']:
                print(f"  ❌ {item}")

        return 0 if not results['failed'] else 1

    # Run validation
    if args.validate:
        print(f"\nRunning validation on {len(target_agents)} agent(s)...\n")

        results = deployer.run_validation(target_agents)

        for agent, result in results.items():
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            print(f"{agent}: {status}")

            if not result["success"] and result["error"]:
                print(f"  Error: {result['error'][:200]}")

        return 0

    # Inventory
    if args.inventory:
        print("\n" + "=" * 80)
        print("Tool Inventory Across Squad")
        print("=" * 80)

        # Get list of all tools locally
        local_tools = []
        if deployer.workspace_dir.exists():
            for item in deployer.workspace_dir.iterdir():
                if item.is_dir() and not item.name.startswith("_"):
                    local_tools.append(item.name)

        print(f"\nLocal tools: {len(local_tools)}")
        for tool in sorted(local_tools):
            print(f"  - {tool}")

        print(f"\nChecking installation on agents...\n")

        for agent in target_agents:
            print(f"{agent}:")
            for tool in sorted(local_tools)[:5]:  # Limit to 5 for brevity
                result = deployer.check_tool_installed(agent, tool)
                status = "✅" if result["installed"] else "❌"
                print(f"  {status} {tool}")
            if len(local_tools) > 5:
                print(f"  ... and {len(local_tools) - 5} more")

        print("\n" + "=" * 80)
        return 0

    # If no action specified, show help
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
