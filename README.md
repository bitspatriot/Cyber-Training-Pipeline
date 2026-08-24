# Cyber-Training-Pipeline

Project BLUF

This repository is the single source of truth for building the analyst training environment from scratch — every install command, configuration, and build log lives here. A separate team should be able to clone this repo and rebuild the entire environment from the documentation alone, without asking a single question.

Environment Prerequisites

Before using this repository, the following must be installed on the host machine:

VS Code — primary IDE (winget install Microsoft.VisualStudioCode)
Git — version control (winget install --id Git.Git -e --source winget)
Markdown All in One — VS Code extension for editing this documentation
A GitHub account with an SSH key registered (ed25519)
Tailscale — secure overlay network for remote access
gitleaks — secrets scanning
Module Directory
00_Docs_and_Tools/ — Project documentation and tooling notes. Holds this README and the reference material for the toolchain setup.
01_Local_Environment/ — Local workstation setup: the exact install commands from Task 0.1 and the SSH key generation/verification notes from Task 0.2. The private key never leaves the machine and is never committed.

Each phase of the pipeline adds another numbered module folder. This list is kept current as folders appear.

Secrets Handling

Nothing that grants access is ever committed to this repository — no keys, tokens, .tfstate, or .env files, even briefly. A committed secret is an incident, not a documentation error, because git history retains it.

Credentials are stored and injected via:

Environment variables for runtime secrets.
A local, untracked .env file — listed in .gitignore, never staged. Teammates cloning this repo create their own .env locally; a sample of the expected variable names (never values) can be provided separately.

The repository-root .gitignore blocks, at minimum: *.pem, *.key, id_rsa*, .env, *.tfstate, *.tfstate.backup, terraform.tfvars, and *credentials*. A clean gitleaks scan against full history is recorded in the documentation.

Remote Access Procedures

Remote access to the office workstation runs over a Tailscale overlay network (to bypass the base commercial NAT) into Windows Remote Desktop. The office workstation is the RDP server; the home machine is the client.

Setup summary:

Install and authenticate Tailscale on the office workstation to join the private tailnet.
Enable Remote Desktop on the workstation; confirm the user account has connect permission and Windows Defender Firewall allows inbound RDP.
Install Tailscale on the home machine under the same account, retrieve the workstation's 100.x.x.x Tailscale IP, and connect with the Remote Desktop client.

Host hardening (required for the server to stay reachable):

Never sleep/hibernate on AC power — configured via the Windows powercfg command-line utility.
Auto power-on after an outage — BIOS/UEFI "Restore on AC Power Loss" set to Power On.
Tailscale unattended mode — enabled so the machine rejoins the tailnet after an unattended reboot.
Key expiry disabled — turned off for this node in the Tailscale admin console so an expired key never drops the device off the tailnet.
Known Issues / Troubleshooting

A living log of what broke and how it was fixed. Each entry: symptom, cause, exact fix.

Symptom	Cause	Fix
--push enabled but no commits found on gh repo create	Ran from an empty/uninitialized directory with no commits	Move into the project folder, git init, git add ., git commit, then re-run
nothing to commit on first commit	No files staged (empty folder or all ignored)	Verify files exist with git status; check .gitignore with git status --ignored
ssh.exe: command not found / mangled C:WindowsSystem32OpenSSHssh.exe on push	core.sshCommand path had backslashes stripped	Set git config --global core.sshCommand ssh, or use the full path with forward slashes