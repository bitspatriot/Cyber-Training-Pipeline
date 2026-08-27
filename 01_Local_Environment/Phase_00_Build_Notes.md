*** Install the IDE and Toolchain from CLI ***
- Install **VS Code**. 
	1. Open Command Prompt: winget install Microsoft.VisualStudioCode
	2. Verify: code --version
- Install **Git**.
	1. Open Command Prompt: winget install --id Git.Git -e --source winget
	2. git --version
- Install the **Markdown All in One** VS Code extension — also from the command line, not from the Extensions sidebar.
	1. Open Terminal in VS Code (Click "View' > 'Terminal')
	2. code --install-extension yzhang.markdown-all-in-one

**** The exact key-generation command you ran — generate an **ed25519** key — and the comment you tagged it with ****

	1. Use VSCode Terminal (PowerShell)
    2. ssh-keygen -t ed25519 -C [GitHub Email Address]
    3. Key pair (public and private) stored: C:\Users\[username]\.ssh\id_ed25519

*** CLI and GUI Steps: Add the public key to GitHub. This step is in the web GUI — document it as a GUI step ***

    1. Launch PowerShell an Administrator
    2. Get-Service -Name ssh-agent | Set-Service -StartupType Manual
    3. Start-Service ssh-agent
    4. Switch back to Command Prompt without elevated permissions
    5. ssh-add c:\Users\[user account]\.ssh\id_ed25519
    6. From VS Code Terminal or Command Prompt: git config --global core.sshCommand "C:\Windows\System32\OpenSSH\ssh.exe"
    7. From VS Code Terminal or Command Prompt: git config --global gpg.ssh.program "C:\Windows\System32\OpenSSH\ssh.exe"
    8. From VS Code Terminal or Command Prompt: cat C:\Users\bitsp\.ssh\id_ed25519.pub | clip
    9. Login into GitHub and add the clipped public key to the Settings > 'SSH and GPG Keys'

*** The exact command you used to verify the connection over SSH, and the success message you expected to see ***

    1. From VS Code Terminal or Command Prompt:
    2. ssh -T git@github.com
    3. The authenticity of host 'github.com (140.82.113.4)' can't be established.
    4. ED25519 key fingerprint is SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU.
    5. This key is not known by any other names.
    6. Are you sure you want to continue connecting (yes/no/[fingerprint])? yes
    7. Warning: Permanently added 'github.com' (ED25519) to the list of known hosts.
    8. Hi [GitHub username]! You've successfully authenticated, but GitHub does not provide shell access.
