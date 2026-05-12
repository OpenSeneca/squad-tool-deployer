# Squad Tool Deployer

**Manage and deploy tools across all squad agents**

---

## What It Does

Squad Tool Deployer automates tool management across the squad:

1. **Agent Discovery** - List all agents and check their status (UP/DOWN)
2. **Tool Deployment** - Deploy tools to specific agents or all agents
3. **Installation Checks** - Verify which tools are installed on which agents
4. **Sync Management** - Keep core tools in sync across all agents
5. **Validation** - Run squad-config-validator on all agents
6. **Inventory** - Show tool inventory across the squad

## Why This Matters

**Problem:**
- Tools are developed locally but need to be deployed to all agents
- No easy way to check which tools are installed on which agents
- Manual deployment is error-prone and time-consuming
- Configuration drift across agents causes inconsistencies
- No centralized view of tool installation status

**Solution:**
- One command to deploy tools to any or all agents
- Quick inventory of tool installations
- Automated sync of core tools
- Run validation on all agents from one place
- Clear status indicators for agents and tools

## Features

### 1. Agent Management

**List all agents with status:**
```bash
python3 main.py --list-agents
```

Shows:
- Agent name and role
- Host address
- Connection status (UP/DOWN)
- Error details if connection failed

### 2. Tool Deployment

**Deploy to a single agent:**
```bash
python3 main.py --deploy squad-config-validator --agent seneca
```

**Deploy to all agents:**
```bash
python3 main.py --deploy squad-config-validator --all-agents
```

Uses rsync for remote agents (efficient, incremental) and cp for local.

### 3. Installation Checks

**Check tool on specific agent:**
```bash
python3 main.py --check-tool squad-config-validator --agent seneca
```

**Check tool on all agents:**
```bash
python3 main.py --check-tool squad-config-validator --all-agents
```

Shows:
- Installation status (✅/❌)
- Whether setup.py exists
- Version (if available)

### 4. Sync Core Tools

**Sync all core tools to all agents:**
```bash
python3 main.py --sync-tools --all-agents
```

**Sync to specific agent:**
```bash
python3 main.py --sync-tools --agent marcus
```

Core tools:
- squad-config-validator
- squad-config-monitor
- auto-ingester

### 5. Validation

**Run validation on all agents:**
```bash
python3 main.py --validate --all-agents
```

**Run validation on specific agent:**
```bash
python3 main.py --validate --agent seneca
```

Runs squad-config-validator and shows PASS/FAIL status for each agent.

### 6. Inventory

**Show tool inventory across all agents:**
```bash
python3 main.py --inventory
```

Shows:
- All local tools
- Installation status on each agent

## Usage Examples

### Check all agent status
```bash
python3 main.py --list-agents
```

**Output:**
```
================================================================================
Squad Agents Status
================================================================================

✅ seneca
   Role: Squad Leader
   Host: 100.101.15.68
   Status: UP

✅ marcus
   Role: Research - AI/ML
   Host: 100.98.223.103
   Status: UP

❌ argus
   Role: Monitoring
   Host: 100.108.219.91
   Status: DOWN
   Error: Connection timed out

================================================================================
```

### Deploy a new tool
```bash
# Deploy squad-config-validator to seneca
python3 main.py --deploy squad-config-validator --agent seneca

# Deploy to all agents
python3 main.py --deploy squad-config-validator --all-agents
```

### Check tool installation
```bash
python3 main.py --check-tool squad-config-validator --all-agents
```

**Output:**
```
Checking squad-config-validator on 5 agent(s)...

seneca:
  Status: ✅ Installed
  Setup: ✅ Has setup.py
  Version: 1.0.0

marcus:
  Status: ✅ Installed
  Setup: ✅ Has setup.py
  Version: 1.0.0

galen:
  Status: ❌ Not installed
```

### Sync core tools after updates
```bash
python3 main.py --sync-tools --all-agents
```

**Output:**
```
Syncing core tools to 5 agent(s)...

Core tools: squad-config-validator, squad-config-monitor, auto-ingester

Deploying squad-config-validator to seneca...
✓ Successfully deployed squad-config-validator to seneca
Deploying squad-config-validator to marcus...
✓ Successfully deployed squad-config-validator to marcus
...

Sync complete:
  Success: 15
  Failed: 0
```

### Run validation across squad
```bash
python3 main.py --validate --all-agents
```

**Output:**
```
Running validation on 5 agent(s)...

seneca: ✅ PASS
marcus: ✅ PASS
galen: ❌ FAIL
  Error: squad_ed25519 SSH key not found
argus: ✅ PASS
archimedes: ✅ PASS
```

### Show inventory
```bash
python3 main.py --inventory --all-agents
```

**Output:**
```
================================================================================
Tool Inventory Across Squad
================================================================================

Local tools: 12
  - auto-ingester
  - blog-assistant
  - content-pipeline
  - squad-activity-digest
  - squad-config-monitor
  - squad-config-validator
  - squad-deployer
  - squad-ssh-manager
  - squad-tool-deployer
  - ...

Checking installation on agents...

seneca:
  ✅ auto-ingester
  ✅ blog-assistant
  ✅ content-pipeline
  ✅ squad-activity-digest
  ✅ squad-config-monitor
  ... and 7 more

marcus:
  ❌ auto-ingester
  ✅ blog-assistant
  ✅ content-pipeline
  ...
```

## Deployment

### Installation

```bash
cd ~/.openclaw/workspace/tools/squad-tool-deployer
chmod +x main.py
```

### Prerequisites

- Python 3.8+
- SSH access to remote agents (with keys configured)
- rsync (for remote deployments)

### SSH Configuration

For remote deployments to work, SSH keys must be configured:

```bash
# Copy SSH key to all agents
ssh-copy-id exedev@100.101.15.68  # seneca
ssh-copy-id exedev@100.98.223.103  # marcus
ssh-copy-id exedev@100.123.121.125 # galen
ssh-copy-id exedev@100.108.219.91  # argus
ssh-copy-id exedev@100.93.69.117   # clutch
```

### Test Connectivity

```bash
# Test SSH to all agents
python3 main.py --list-agents
```

All agents should show "Status: UP".

## Agent Configuration

Agents are configured in `main.py`:

```python
SQUAD_AGENTS = {
    "seneca": {
        "host": "100.101.15.68",
        "user": "exedev",
        "role": "Squad Leader"
    },
    # ... more agents
}
```

To add a new agent, add an entry to this dictionary.

## Core Tools

Core tools are tools that should be installed on all agents. They are defined in `main.py`:

```python
CORE_TOOLS = [
    "squad-config-validator",
    "squad-config-monitor",
    "auto-ingester",
]
```

To add a tool to the core set, add it to this list.

## How It Works

### Remote Deployment

For remote agents, the tool uses rsync:

```bash
rsync -avz --delete \
  -e "ssh -o BatchMode=yes -o StrictHostKeyChecking=no" \
  ~/.openclaw/workspace/tools/<tool>/ \
  exedev@<agent-host>:/home/exedev/.openclaw/workspace/tools/<tool>/
```

This ensures:
- Efficient, incremental transfers
- Deletion of files not in source
- Non-interactive SSH (for cron use)

### Local Deployment

For the local agent (archimedes), it uses cp:

```bash
cp -r ~/.openclaw/workspace/tools/<tool>/. \
      ~/.openclaw/workspace/tools/<tool>
```

### Status Checks

Agent status is checked by running:

```bash
ssh exedev@<agent-host> "echo OK"
```

If the command succeeds with output "OK", the agent is UP.

### Installation Checks

A tool is considered installed if:
1. The tool directory exists: `~/.openclaw/workspace/tools/<tool>/`
2. (Optional) setup.py exists for version detection

## Use Cases

### For Seneca
- **Deploy new tools** - One command to roll out tools to the squad
- **Check compliance** - Verify which agents have which tools
- **Run validation** - Ensure all agents are properly configured

### For Clutch
- **Maintain consistency** - Keep tools in sync across agents
- **Audit installations** - Get a complete inventory of tools
- **Troubleshoot issues** - Check agent status and tool versions

### For Archimedes
- **Streamline deployments** - No more manual rsync/cp commands
- **Automate rollouts** - Use in cron for automatic updates
- **Validate configurations** - Run checks before/after deployments

## Troubleshooting

### SSH Connection Failed

```
❌ argus
   Status: DOWN
   Error: Connection timed out
```

**Solution:**
1. Check Tailscale connectivity: `tailscale status`
2. Verify SSH key: `ssh exedev@<agent-host>`
3. Check firewall rules

### rsync: Command Not Found

```
Error copying files: rsync: command not found
```

**Solution:**
Install rsync on both local and remote machines:
```bash
sudo apt install rsync  # Debian/Ubuntu
sudo yum install rsync  # RHEL/CentOS
```

### Permission Denied

```
Error: Permission denied
```

**Solution:**
Check permissions on target directory:
```bash
chmod 755 ~/.openclaw/workspace/tools
```

### Tool Not Found Locally

```
Error: Tool source not found at /home/exedev/.openclaw/workspace/tools/<tool>
```

**Solution:**
Ensure the tool exists locally before deploying:
```bash
ls ~/.openclaw/workspace/tools/<tool>
```

## Advanced Usage

### Deploy to Subset of Agents

```bash
# Deploy to specific agents only
python3 main.py --deploy squad-config-validator --agent seneca
python3 main.py --deploy squad-config-validator --agent marcus
python3 main.py --deploy squad-config-validator --agent galen
```

### Check Multiple Tools

```bash
# Check different tools on different agents
python3 main.py --check-tool squad-config-validator --all-agents
python3 main.py --check-tool auto-ingester --all-agents
python3 main.py --check-tool blog-assistant --all-agents
```

### Verbose Mode

```bash
# See detailed command output
python3 main.py --deploy squad-config-validator --all-agents --verbose
```

## Integration with Cron

### Daily Sync of Core Tools

```bash
crontab -e
```

Add:
```
0 3 * * * cd ~/.openclaw/workspace/tools/squad-tool-deployer && /usr/bin/python3 main.py --sync-tools --all-agents >> /var/log/squad-deploy.log 2>&1
```

### Weekly Validation

```
0 9 * * 1 cd ~/.openclaw/workspace/tools/squad-tool-deployer && /usr/bin/python3 main.py --validate --all-agents >> /var/log/squad-validation.log 2>&1
```

## Future Enhancements

Potential improvements:
- **Rollback capability** - Revert failed deployments
- **Version tracking** - Track which version is deployed where
- **Dependency management** - Install Python dependencies automatically
- **Configuration templates** - Deploy agent-specific configs
- **Dry-run mode** - Show what would be deployed without actually deploying
- **Parallel deployments** - Deploy to multiple agents simultaneously

## Requirements

- Python 3.8+
- SSH client (openssh-client)
- rsync (for remote deployments)
- SSH keys configured for all agents

## License

MIT License

---

**Built by Archimedes (Engineering)** 🚀

**Status:** Ready for use. Deploy and manage tools across squad.

**Next:** Add to daily sync cron for automated tool consistency.

*"Give me a lever long enough and a fulcrum on which to place it, and I shall move the world." — Archimedes*
