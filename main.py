#!/usr/bin/env python3
"""
Squad Tool Deployer
Manages tool deployment across all squad agents.

Features:
- Agent discovery
- Tool deployment to single/all agents
- Installation checks
- Sync core tools
- Run validation
- Inventory

Uses rsync for remote, cp for local.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Squad agents configuration (using Tailscale IPs)
AGENTS = {
    "marcus": {"host": "100.98.223.103", "user": "exedev", "type": "ssh"},
    "seneca": {"host": "100.101.15.68", "user": "exedev", "type": "ssh"},
    "galen": {"host": "100.123.121.125", "user": "exedev", "type": "ssh"},
    "argus": {"host": "100.108.219.91", "user": "exedev", "type": "ssh"},
    "clutch": {"host": "100.87.144.118", "user": "exedev", "type": "ssh"},
    "archimedes": {"host": "localhost", "user": "exedev", "type": "local"},
}

# Core tools to sync
CORE_TOOLS = [
    "squad-config-validator",
    "squad-config-monitor",
    "auto-ingester",
]

# Workspace paths
WORKSPACE = Path.home() / ".openclaw" / "workspace"
TOOLS_DIR = WORKSPACE / "tools"
LOG_DIR = WORKSPACE / "logs"


def run_command(cmd, capture=True, timeout=10):
    """Run a shell command with timeout."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=capture,
            text=True,
            timeout=timeout,
        )
        if capture:
            return result.stdout, result.returncode
        return None, result.returncode
    except subprocess.TimeoutExpired:
        if capture:
            return None, 1
        return None, 1
    except Exception as e:
        if capture:
            return str(e), 1
        return None, 1


def check_ssh_agent(agent_name, agent_config):
    """Check if SSH agent is reachable."""
    if agent_config["type"] == "local":
        return True, "Local agent"

    host = agent_config["host"]
    user = agent_config["user"]

    # Check ping
    stdout, _ = run_command(f"ping -c 1 -W 2 {host} 2>/dev/null", timeout=5)
    if stdout is None:
        return False, "SSH connection failed (timeout)"

    # Check SSH connectivity
    stdout, returncode = run_command(
        f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no {user}@{host} 'echo ok'",
        timeout=10
    )

    if returncode == 0:
        return True, "SSH connection OK"
    else:
        return False, f"SSH connection failed (code {returncode})"


def list_agents():
    """List all squad agents with their status."""
    print("=" * 60)
    print("Squad Agent Status")
    print("=" * 60)
    print(f"{'Agent':<12} {'Host':<15} {'Type':<8} {'Status':<20}")
    print("-" * 60)

    for agent_name, config in AGENTS.items():
        status_ok, status_msg = check_ssh_agent(agent_name, config)
        status_icon = "✓" if status_ok else "✗"
        print(f"{agent_name:<12} {config['host']:<15} {config['type']:<8} {status_icon} {status_msg:<18}")

    print("=" * 60)


def deploy_tool(tool_name, agent_name=None, dry_run=False):
    """Deploy a tool to one or all agents."""
    tool_path = TOOLS_DIR / tool_name

    if not tool_path.exists():
        print(f"✗ Tool not found: {tool_name}")
        return False

    targets = [agent_name] if agent_name else AGENTS.keys()

    for target in targets:
        if target not in AGENTS:
            print(f"✗ Unknown agent: {target}")
            continue

        agent_config = AGENTS[target]

        if dry_run:
            print(f"[DRY RUN] Would deploy {tool_name} to {target}")
            continue

        print(f"Deploying {tool_name} to {target}...")

        if agent_config["type"] == "local":
            # Use cp for local
            target_dir = WORKSPACE / "tools" / tool_name
            stdout, returncode = run_command(f"cp -r {tool_path} {target_dir}")
            if returncode == 0:
                print(f"  ✓ Deployed to local {target_dir}")
            else:
                print(f"  ✗ Failed: {stdout}")
        else:
            # Use rsync for remote
            host = agent_config["host"]
            user = agent_config["user"]
            remote_tools_dir = f"{user}@{host}:.openclaw/workspace/tools"

            stdout, returncode = run_command(
                f"rsync -avz --delete {tool_path}/ {remote_tools_dir}/{tool_name}/",
                timeout=30
            )
            if returncode == 0:
                print(f"  ✓ Deployed to {host}")
            else:
                print(f"  ✗ Failed: {stdout}")

    return True


def check_installation(agent_name, tool_name):
    """Check if a tool is installed on an agent."""
    agent_config = AGENTS[agent_name]

    if agent_config["type"] == "local":
        tool_path = TOOLS_DIR / tool_name / "main.py"
        if tool_path.exists():
            return True, "Installed"
        return False, "Not found"

    host = agent_config["host"]
    user = agent_config["user"]

    stdout, returncode = run_command(
        f"ssh {user}@{host} 'test -f .openclaw/workspace/tools/{tool_name}/main.py && echo found'",
        timeout=10
    )

    if stdout and "found" in stdout:
        return True, "Installed"
    return False, "Not found"


def inventory(agent_name=None):
    """Show inventory of tools on one or all agents."""
    targets = [agent_name] if agent_name else AGENTS.keys()

    print("=" * 60)
    print("Tool Inventory")
    print("=" * 60)

    for target in targets:
        if target not in AGENTS:
            continue

        print(f"\n{target}:")
        print(f"  {'Tool':<30} {'Status':<10}")
        print("  " + "-" * 40)

        for tool_name in CORE_TOOLS:
            installed, status = check_installation(target, tool_name)
            icon = "✓" if installed else "✗"
            print(f"  {icon} {tool_name:<29} {status:<10}")

    print("=" * 60)


def validate_agent(agent_name):
    """Run validation checks on an agent."""
    print(f"\nValidating {agent_name}...")

    status_ok, status_msg = check_ssh_agent(agent_name, AGENTS[agent_name])
    print(f"  Connection: {status_msg}")
    if not status_ok:
        return False

    all_installed = True
    for tool_name in CORE_TOOLS:
        installed, status = check_installation(agent_name, tool_name)
        print(f"  {tool_name}: {status}")
        if not installed:
            all_installed = False

    return all_installed


def sync_tools(agent_name=None, all_agents=False, dry_run=False):
    """Sync core tools to agents."""
    targets = []

    if all_agents:
        targets = list(AGENTS.keys())
    elif agent_name:
        targets = [agent_name]
    else:
        print("Error: Specify --agent or --all-agents")
        return False

    print("=" * 60)
    print("Syncing Core Tools")
    print("=" * 60)
    print(f"Tools: {', '.join(CORE_TOOLS)}")
    print(f"Targets: {', '.join(targets)}")
    print("=" * 60)

    # Deploy each tool to each target
    for target in targets:
        for tool_name in CORE_TOOLS:
            print(f"\n{tool_name} -> {target}:")
            deploy_tool(tool_name, target, dry_run=dry_run)

    print("=" * 60)
    print("Sync complete")
    print("=" * 60)

    return True


def main():
    parser = argparse.ArgumentParser(description="Squad Tool Deployer")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # List agents
    subparsers.add_parser("list-agents", help="List all squad agents")

    # Deploy tool
    deploy_parser = subparsers.add_parser("deploy", help="Deploy a tool")
    deploy_parser.add_argument("tool", help="Tool name to deploy")
    deploy_parser.add_argument("--agent", help="Target agent (default: all)")
    deploy_parser.add_argument("--dry-run", action="store_true", help="Dry run")

    # Sync tools
    sync_parser = subparsers.add_parser("sync-tools", help="Sync core tools")
    sync_parser.add_argument("--agent", help="Target agent")
    sync_parser.add_argument("--all-agents", action="store_true", help="Sync to all agents")
    sync_parser.add_argument("--dry-run", action="store_true", help="Dry run")

    # Inventory
    inv_parser = subparsers.add_parser("inventory", help="Show tool inventory")
    inv_parser.add_argument("--agent", help="Target agent (default: all)")

    # Validate
    val_parser = subparsers.add_parser("validate", help="Validate agent setup")
    val_parser.add_argument("agent", help="Agent to validate")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "list-agents":
        list_agents()
    elif args.command == "deploy":
        deploy_tool(args.tool, args.agent, args.dry_run)
    elif args.command == "sync-tools":
        sync_tools(args.agent, args.all_agents, args.dry_run)
    elif args.command == "inventory":
        inventory(args.agent)
    elif args.command == "validate":
        validate_agent(args.agent)


if __name__ == "__main__":
    main()
