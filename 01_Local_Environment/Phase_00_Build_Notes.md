# Task 0.1: The IDE and Toolchain

*** Install the IDE and Toolchain from CLI ***
1. Install **VS Code**. 
	-  Open Command Prompt: winget install Microsoft.VisualStudioCode
	- Verify: code --version2. Install **Git**.
2. Open Command Prompt: winget install --id Git.Git -e --source winget
	-  git --version
3.  Install the **Markdown All in One** VS Code extension — also from the command line, not from the Extensions sidebar.
	-  Open Terminal in VS Code (Click "View' > 'Terminal')
	-  code --install-extension yzhang.markdown-all-in-one

**** The exact key-generation command you ran — generate an **ed25519** key — and the comment you tagged it with ****

	1. Use VSCode Terminal (PowerShell)
    2. ssh-keygen -t ed25519 -C [GitHub Email Address]
    3. Key pair (public and private) stored: C:\Users\[username]\.ssh\id_ed25519

# Task 0.2: Auth & Version Control

*** CLI and GUI Steps: Add the public key to GitHub. This step is in the web GUI — document it as a GUI step ***

    1. Launch PowerShell an Administrator
    2. Get-Service -Name ssh-agent | Set-Service -StartupType Manual
    3. Start-Service ssh-agent
    4. Switch back to Command Prompt without elevated permissions
    5. ssh-add c:\Users\[user account]\.ssh\id_ed25519
    6. From VS Code Terminal or Command Prompt: git config --global core.sshCommand ssh
    7. From VS Code Terminal or Command Prompt: git config --global gpg.ssh.program ssh
    8. From VS Code Terminal or Command Prompt: cat C:\Users\sandbox_user\.ssh\id_ed25519.pub | clip
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

# Task 0.3: Repository Initialization

*** Authenticate and Initialize Repository ***

    1. Launch GitBash Bash Terminal in VS Code: User drop down right next to "+" icon in the VS Code Terminal and select "GitBash"
    2. Command: gh auth login (If you get error that 'gh' isn't a recognized command, restart VSCode)
    3. Follow the Prompts to authenticate with SSH Public Key:
    How would you like to authenticate GitHub CLI? (Select 'Login with a web browser')                                                                                                     
    ! First copy your one-time code: 9690-8A16                                                  
    Press Enter to open https://github.com/login/device in your browser...                      
    ? Authentication complete.
    ? gh config set -h github.com git_protocol ssh
    ? Configured git protocol
    ? SSH key already existed on your GitHub account: C:\Users\bitsp\.ssh\id_ed25519.pub
    ? Logged in as bitspatriot

*** Set the `user.name` and `user.email` that Git stamps onto every commit ***

1. git config --global user.email �justin@bitspatriot.com�
2. git config --global user.name "Justin Jackson"

# Task 0.4: The README Standard
*** Create the 'Cyber-Training-Pipeline' repository and add README file to the Folder ***

1. From VSCode (Powershell terminal) mkdir Cyber-Training-Pipeline && cd Cyber-Training-Pipeline
2. echo "# Cyber-Training-Pipeline" >> README.md
3. Switch to VSCode GitBash terminal
4. git init
5. git add README.md
6. git commit -m "First commit"
7. gh repo create "Cyber-Training-Pipeline" --private --source=. --remote=origin --push 

*** Create the .gitignore file and push it to the repository ***

1. Create the .gitignore file in the local 'Cyber-Training-Pipeline' directory:
2. cat > .gitignore << 'EOF' *.pem *.key id_rsa .env *.tfstate *.tfstate.backup terraform.tfvars *credentials* EOF
2. git add .gitignore
3. git commit -m "Add .gitignore for secrets ad terraform state"
4. git push

*** Create two new folders in GitHub from the GUI ***

1. Create two new folders locally in the 'Cyber-Training-Pipeline' directory from the VSCode terminal: 'mkdir 00_Docs_and_Tools && mkdir 01_Local_Environment'
2. Log into GitHub
3. Navigate to the 'Cyber-Training-Pipeline' repository
4. Create the folder `00_Docs_and_Tools`
5. Create the folder `01_Local_Environment`

# Task 0.5: GUI vs CLI

1. Practice making changes, commiting them, and pull/pushing then through VS Code "Source Control" and the VS Code terminal (GitBash).

# Task 0.6: Establishing the Remote Workspace

*** Setup remote access on your Windows workstation with Tailscale ***

1. From Windows Command Line: winget install tailscale.tailscale
2. Follow tailscale instalation instructions on the server and client to ensure connection through the Tailscale dashboard, and test RDP connection.
3. *** IMPORTANT ***: Ensure that "Run unattended" is selected in Tailscale, or else you VPN connection can be disconnected after a system reboot.

# Task 0.7: Secrets Hygiene

*** Install Gitleaks and run against the repository on Infra_Node ***

1. cd /tmp
2. wget https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz (Check https://github.com/gitleaks/gitleaks/releases for the latest release)
3. tar xzf gitleaks_8.28.0_linux_x64.tar.gz
4. sudo mv gitleaks /usr/local/bin/
5. gitleaks version
6. Git isn't installed on Infra_Node: sudo apt install git
7. Navigate to repository folder on Infra_Node. If not yet cloned, clone the repo to /tmp/: 
   - git clone <repo-url> squadron-lab-scan
   - cd squadron-lab-scan
8. Navigate to squadron-lab-scan
9. Ensure all of the repository's commit history is present:
   - git log --oneline
   - git reve-list --count HEAD
10. If all history is present, run gitleaks agains the repository clone: gitleaks detect --source . --report-format json --report-path /tmp/gitleaks-report.json --verbose; echo "gitleaks exit code: $?"
11. Confirm that ther's 0 findings
12. Keep the gitleaks report that was created, but delete the clone, so there's isn't a second copy of potentially exposed secrets.

