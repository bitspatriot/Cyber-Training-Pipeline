# Task 2.1: Caddy Web Server

*** Install the caddy repository and web server ***
1. sudo dnf install -y 'dnf-command(copr)'
2. sudo dnf copr enable -y @caddy/caddy
3. sudo dnf install -y caddy
4. Verify Install: caddy version

*** Create the HTML page ***
1. sudo mkdir -p /var/www/html
2. Create index.html file in /var/www/html (Caddy 'index.html' page pushed to '02_Config_Files -> 'caddy_web_Server')
3. Configure the Caddfile that listens on port :8080 from all hosts, and not just 'localhost.'
   - New Caddy file created to replace existing /etc/caddy/Caddyfile ('Caddyfile' pushed to '02_Config_Files -> 'caddy_web_Server')
4. Validate the Caddyfile config: caddy validate --config /etc/caddy/Caddyfile
5. SELINUX (Rocky) tripwires: SELINUX can block serving websites from certain directories, or from binding to a non-standarp port (e.g. 8080) Fixes:
   - ls -Zd /var/www/html
   - sudo restorecon -Rv /var/www/html
   - sudo semanage port -l | grep http_port_t
   - If 8080 isn't listed in http_port_t: sudo semanage port -a -t http_port_t -p tcp 8080

*** Start Caddy ***
1. sudo systemctl enable --now caddy
2. sudo systemctl status caddy --no-pager
3. Confirm the web server is listening on port 8080: sudo ss -tlnp | grep :8080
- Should see: 0.0.0.0:8080 (or *:8080) — not 127.0.0.1:8080

*** Open the firewall to enable "answers off-box" capability ***
1. Confirm host firewall that's active: sudo systemctl is-active firewalld nftables (Should be firewalld for Rocky Linux)
2. sudo firewall-cmd --permanent --add-port=8080/tcp
3. sudo firewall-cmd --reload
4. sudo firewall-cmd --list-ports    
5. Verify: confirm '8080/tcp' present

*** Prove the web server answeres requests from the Infra_Node ***
1. Install 'curl': sudo apt install curl
2. From the Infra_Node: curl -v http://10.10.30.x:8080/
3. Should she '200 OK' and the contents of index.html

# Task 2.2: Network-Wide DNS Spoofing
1. sudo nano /etc/dnsmasq.conf
2. Bind Data_Node IP lease so it doesn't receive a new address and break the spoofing at the end it's 12H lease: dhcp-host=<data-node-MAC>,data-node,10.10.30.116 (or whatever Data_Node's IP is)
   - Grab MAC from dnsmasq if unknown: grep 10.10.30.116 /var/lib/misc/dnsmasq.leases
   - If you bound Data_Node to a new IP, force it to pick up the new reservation: sudo nmcli device reapply <iface>
3. sudo /usr/local/sbin/dnsmasq --test
4. sudo systemctl restart dnsmasq
5. Install 'dig': sudo apt install dnsutils
6. Verify the spoo resolves from the Infra_Node: dig @10.10.30.1 update.microsoft.com +short
   - Should return <Data_Node IP> and not the real microsoft address

*** Disable IPv6 on the Windows_Node's Lab_Internal adapter from Powershell ***
1. Find the Lab_Internal adapter name: Get-NetAdapter
2. Disable-NetAdapterBinding -Name "vEthernet (Lab_Internal)" -ComponentID ms_tcpip6
3. Confirm IPv6 is disabled: Get-NetAdapterBinding -Name "vEthernet (Lab_Internal)" -ComponentID ms_tcpip6
4. ipconfig /flushdns
5. From Windows_Node: Confirm the poisioned DNS spoof resolves: Resolve-DnsName update.microsoft.com
   - Should return the Data_Nodes IP (10.10.30.116)

*** Request Microsoft website from Powershell ***
1. Invoke-WebRequest -Uri "http://update.microsoft.com:8080" -UseBasicParsing
2. Test #1 (from Powershell):
   - $r = Invoke-WebRequest -Uri "http://update.microsoft.com:8080" -UseBasicParsing
   - $r.StatusCode (should see 200)
   - $r.Content (should see the HTML you put in /var/www/html/index.html)
3. Test #2 (from Powershell):
- "Resolved to: $((Resolve-DnsName update.microsoft.com).IPAddress)" 
- (Invoke-WebRequest -Uri "http://update.microsoft.com:8080" -UseBasicParsing).Content

# Task 2.3: The Bastion Pattern

*** Establish the Host can reach Infra_Node ***
1. Infra_Node Host Interface (eth1): 172.17.250.19/20 (Not Lab_Internal 10.10.30.1/24 interface (eth0))
   - If the Default Switch IP is NAT's and can chage if the workstation IP is given a new DHCP lease from the enterprise LAN. Keep this in mind for the future.

*** Enable OpenSSH on the Windows 11 Host (Powershell) ***
1. Check if OpenSSH client is already intalled: Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Client*'
   - If not: Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
   - Verify install: ssh -V

*** Generate a key pair on the Host workstation and set a passphrase this time ***
1. ssh-keygen -t ed25519 -C "host-workstation -> infra-node"
   - Accept default key location
   - Don't forget to set a passphrase when prompted

*** Authorize the Host's public key on the Infra_Node ***
1. Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub
2. ssh sandbox_user@<INFRA_NODE_DEFAULT_IP> "echo 'PASTE_PUBKEY_LINE' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
3. ssh sandbox_user@<INFRA_NODE_DEFAULT_IP>

*** Configure OpenSSH agent on the Host ***
1. Set-Service ssh-agent -StartupType Automatic
2. Start-Service ssh-agent
3. Confirm: Get-Service ssh-agent
4. Add new key to agent so you stop getting prompted for passphrase: ssh-add $env:USERPROFILE\.ssh\id_ed25519
5. List loaded key: ssh-add -l
6. Test: ssh sandbox_user@<INFRA_NODE_DEFAULT_IP> (no longer asks for passphrase)

*** Configure the hop to Data_Node in the SSH configuration - ProxyJump ***
1. Host (Powershell): notepad $env:USERPROFILE\.ssh\config
2. Created Host ssh config file and pushed it to 02_Config_Files\host_ssh in the repository
3. Get your Host's public key over to Data_Node: (NOTE: unable to paste key from the Host to the Infra_Node, which is why the process below is created)
   - Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub
   - cd $env:USERPROFILE\.ssh
   - scp id_ed25519.pub <sanbox_user>@<INFRA_DEFAULT_IP>:/tmp/host.pub
   - SSH to Infra_Node: ssh <sanbox_user>@<INFRA_DEFAULT_IP>
   - cd /tmp
   - Confirm the host.pub file landed on Infra_Node and look at the key: cat /tmp/host.pub
     - Confirm there's a 'host-workstation -> data-node' comment at the end of the key. It will prevent confusion later. If you didn't add it during key creation, add it now.
   - ssh <sandbox_user>@10.10.30.116 "cat >> ~/.ssh/authorized_keys" < /tmp/host.pub
   - Verify the entry in now in the Data_Node's authorized_keys file: ssh <sandbox_user>@10.10.30.116 "cat ~/.ssh/authorized_keys"
     - Should now see three keys, including 'host-workstation -> data-node' entry
   - CLEAN UP: Delete the /tmp/host.pub key

*** Test ProxyJump from the Host ***
1. Should now be able to ssh from the host directly to the Data_Node: ssh data-node
2. Confirm that ProxyJump is being applied to the IP:
   - ssh -G 10.10.30.116 | Select-String "proxyjump|hostname"
   - ssh -G data-node    | Select-String "proxyjump|hostname"
   - Can now see that 'ssh data-node' shows that it's traversing through the bastion, and not being AgentForwarded
3. Task deliverable (Document why ProxyJump is safer): ProxyJump is safer because the bastion is only a transport. It never gains access to your keys or agent. Agent forwarding trusts the bastion with live use of your keys, so a compromised bastion could impersonate you to every system your keys reach. The whole point of a bastion is that it's the exposed, higher-risk box, so you specifically don't want to hand it your credentials. That's why the task mandates ProxyJump and bans forwarding.

*** Record and Regenerate Data_Node's host keys ***
1. On Host: # from the Host, after first connecting via `ssh data-node`, the key is pinned in known_hosts: ssh-keygen -lf $env:USERPROFILE\.ssh\known_hosts
2. On Data_Node (sanity check): sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
   - Note the SHA256 fingerprint in your documents
3. sudo rm /etc/ssh/ssh_host_*
4. sudo ssh-keygen -A (regenerates a fresh set)
5. sudo systemctl restart sshd
   - Note the new SHA256 fingerprint in your documents
6. ssh data-node
   - Host should refuse the connection with a loud man-in-the-middle potential attack warning because the host key that Data_Node pinned has changed.
7. Fix the broken connection by deleting the stale fingerprint and reconnecting from the Host:
   - ssh-keygen -R data-node
   - ssh-keygen -R 10.10.30.116
   - ssh data-node
8. Should now be prompted to accept the new key

*** Fix the Windows_Node scheduled metrics pull from scheduled Task ***
1. Understanding: Regenerating the Data_Node's hosy key breaks Task 1.8 because it's SSH calls now fail.
2. ssh-keygen -R 10.10.30.116
3. ssh-keyscan 10.10.30.116 >> $env:USERPROFILE\.ssh\known_hosts
4. Start-ScheduledTask -TaskName "LabOps-PullMetrics"
5. Get-Content C:\ProgramData\LabOps\metrics.log -Tail 5
   - Should see metrics.log data being ssh'd again on the Windows_Node

# Task 2.4: SSH Local Port Forwarding

NOTE: The hop through Infra_Node with Proxy_Jump is already build, so no additional flags are needed for the SSH tunnel
1. ssh -L 9090:localhost:8080 data-node
   - Leave shell open on the Data_Node. The tunnel exists only when the SSH connection is alive.
2. Open browser on host and got to 'http://localhost:9090'
3. Should see the Caddy page running on the Data_Node. The Host browser thinks it's talking to a local web service listening on port 9090.

# Task 2.5: Headless Packet Capture

*** Install tcpdump on the Infra_Node and start a filtered capture ***
1. Infra_Node: Install tcpdump: which tcpdump || sudo apt install tcpdump -y
2. sudo tcpdump -i eth0 -n -w /tmp/dora-spoof.pcap 'udp port 67 or udp port 68 or udp port 53' (the goal is to capture the full Discover, Offer, Request, Acknowledge (DORA) exchange from DNS and DHCP)
   - Optionally in a second terminal, you can watch the exchange in real time: sudo tcpdump -i eth0 -n 'udp port 67 or udp port 68 or udp port 53'
3. From Windows_Node, force a full DORA:
   - ipconfig /release
   - ipconfig /renew
   - ipconfig /flushdns
   - Invoke-WebRequest -Uri "http://update.microsoft.com:8080" -UseBasicParsing
     - Because the local DNS cache is empty, Windows sends a real DNS query for update.microsoft.com to the Infra_Node, and dnsmasq answers with the spoofed 10.10.30.116 address that's hosts poisioned DNS.
4. Stop the capture on Infra_Node: (Ctrl + C)

*** Pull the /tmp/dora-spoof.pcap back to Window_Node for analyis ***
1. From Infra_Node: sudo chmod 644 /tmp/dora-spoof.pcap
2. From Host: 
   - cd $env:USERPROFILE\Downloads
   - scp infra-node:/tmp/dora-spoof.pcap . (Get used to using the new Host alias' of infra-node and data-node so you don't have to keep typing the IP of each host)
3. Install Wireshark on the Host: winget install WiresharkFoundation.Wireshark
4. From Powershell: & "C:\Program Files\Wireshark\tshark.exe" -r $env:USERPROFILE\Downloads\dora-spoof.pcap -Y 'dns.qry.name == "update.microsoft.com"'
   - Should see (Wireshark (GUI) screenshot added to '01_Local_Environment' folder in repository):
     - 26 208.767467 10.10.30.118 → 10.10.30.1   DNS 80 Standard query 0x8c1f A update.microsoft.com
     - 27 208.767614   10.10.30.1 → 10.10.30.118 DNS 96 Standard query response 0x8c1f A update.microsoft.com A 10.10.30.116
  
# Task 2.6: Self-Sabotage & Recovery
*** IMPORTANT: Snapshot all your VMs and set a root on the Data_Node. You will get stuck and lose all of your work on the Data_Node if you skip this step!! ***
1. Snapshot VMs in Powershell:
   - Checkpoint-VM -Name Infra_Node -SnapshotName "pre-fstab-break"
   - Checkpoint-VM -Name Data_Node  -SnapshotName "pre-fstab-break"
   - Checkpoint-VM -Name Windows_Node -SnapshotName "pre-fstab-break"
2. Confirm that root account is usable: sudo passwd -S root
3. Output showing "P" means root is usable. Set the password: sudo passwd root

*** Introduce the /etc/fstab typo ***
1. sudo nano /etc/fstab
2. Find the /mnt/ops_data line and alter one hex character in it's UUID (e.g. ...a1b2 -> ...a1c2)
   - My example: changed the first character of the /mnt/ops_data UUID from "d" to "e"
3. Save the /etc/fstab file
4. Reboot the Data_Node: sudo reboot

*** Get a recovery shell ***
1. Data_Node should fail to boot and will ask for root password. Don't enter it
2. Hit Ctrl+Alt+Del to reboot and access the GRUB loader
3. Highlight the default Rocky Linux entry and press "e"
4. Find the kernel line staring with 'linux' and go to the very end of the line
5. Append 'rd.break' to that line
6. Hit Ctrl+X or F10 to reboot
7. 'rd.break' will drop you into a shell
8. The real root directory boots in a read-only state at /sysroot. Mount /sysroot with read+write privileges: 
   - mount -o remount,rw /sysroot
   - chroot /sysroot
9. Fix the UUID typo in /etc/fstab: vim /etc/fstab
10. Save /etc/fstab
11. Test /etc/fstab: mount -a (no error means that fstab mounted cleanly)
12. Reboot: for 'rd.break' method, enter 'exit', and then 'exit' again
13. Data_Node should boot properly:
    - Log into Data_Node and make sure /mnt/ops_data and /mnt/log_data mounted correctly
    - Check status of metrics-logger: systemctl status metrics-logger.service

*** Cleanup VM snapshots ***
1. Remove-VMSnapshot -VMName Data_Node -Name "pre-fstab-break"
2. Remove-VMSnapshot -VMName Infra_Node -Name "pre-fstab-break"
3. Remove-VMSnapshot -VMName Windows_Node -Name "pre-fstab-break"
