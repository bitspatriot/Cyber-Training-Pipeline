# Task 1.1: Install Hyper-V via CLI

1. Launch an elevated command prompt
2. Command: dism.exe /Online /Enable-Feature /FeatureName:Microsoft-Hyper-V /All
3. Open elevated Powershell Window: Verify Hyper-V cmdlets are 	available: Get-Command -Module Hyper-V
4. List Existing Network Adapters: Get-NetAdapter | ft Name, Status
5. Create new Internal Switch: New-VMSwitch -name "Lab_Internal" -SwitchType Internal

# Task 1.2: Create three VMs via CLI (Powershell)

1. Define VM configuration parameters *
$vmName = "MyHeadlessVM"
$memoryAmount = 4GB
$diskSize = 60GB
$path = "C:\Hyper-V\Virtual Machines"

2. Create the VM attached initially to the custom internal switch *
New-VM -Name $vmName `
       -MemoryStartupBytes $memoryAmount `
       -NewVHDPath "$path\$vmName\$vmName.vhdx" `
       -NewVHDSizeBytes $diskSize `
       -SwitchName "Lab_Internal" `
       -Generation 2

*** IMPORTANT: Windows Server requires a Generation 1 to bootstrap the image. Generation 2 can be used for the Debian/Linux VMs. If you create the Windows VM as Generation 2, you'll have to recreate it. ***

*** Add the second network interface for the Hyper-V Default Switch ***
Add-VMNetworkAdapter -VMName $vmName -SwitchName "Default Switch"

*** Optional: Enable Automatic Checkpoints / Set CPU cores ***
Set-VMProcessor -VMName $vmName -Count 2

*** Start the VM headless (in the background, without launching Hyper-V Manager GUI) ***
Note: Start downloading all three ISOs prior to disabling the adapter.

1. Add DVD Drive and Mount ISO to the VM

Debian and Rocky VMs/Nodes
- Add-VMDvdDrive -VMName "Infra_Node" -Path "C:\ISOs\[ISO filename]" -Passthru | ForEach-Object { Set-VMFirmware -VMName $_.VMName -SecureBootTemplate "MicrosoftUEFICertificateAuthority" -FirstBootDevice $_ }

Windows Server VM/Node
- Add-VMDvdDrive -VMName "Windows_Node" -Path "C:\ISOs\[ISO filename]" -Passthru | ForEach-Object { Set-VMFirmware -VMName $_.VMName -SecureBootTemplate "MicrosoftWindows" -FirstBootDevice $_ }

2. Start the VM via CLI: Start-VM -Name $vmName

# Task 1.3: Infra_Node Preparation for DHCP/DNS (Task 1.3)

Discovered Debian Dependencies:
1. sudo isn't installed
2. sources.list isn't populate with URLs needed to download packages
3. username isn't in /etc/sudoers

STEPS:
1. Elevate to root: (su -)
2. Populate /etc/apt/sources.list with the following URLs:
   deb http://deb.debian.org/debian trixie bookworm
   deb http://security.debian.org/debian-security trixie-security main
   deb http://deb.debian.org/debian trixie-updates main
3. Add username to /etc/sudoers file
4. Run 'apt install sudo'
5. Exit root (Ctrl + C) 
6. Run 'sudo apt update'

*** Note: You won't be able to download any packages needed (e.g. dmasq) without performing these preliminary steps ***

*** Bind static IP address to eth1 ***

1. ip -br link
   a. Interface attached to the Hyper-V Default Switch should already have a 172.x.x.x address. The second interface attached to the 'Lab_Internal' switch shouldn't have an IP assigned
2. Navigate to /etc/systemd/network/
3. Create '10-internal.network': touch 10-internal.network
4. [Match]
   Name=[interface attached to Lab_Internal] (e.g. eth0)

   [Network]
   Address=10.10.30.1/24
   DHCP=no
5. sudo systemctl enable --now systemd-networkd
6. sudo systemctl restart systemd-networkd
7. ip -4 addr show eth0 (should now see eth0 with IP address 10.10.10.1)

*** Build dnsmasq from source ***
1. cd /usr/local/src
2. sudo wget https://thekelleys.org.uk/dnsmasq/dnsmasq-2.91.tar.gz
3. sudo tar xzf dnsmasq-2.91.tar.gz
4. cd dnsmasq-2.91
5. Create and configure the /etc/dnsmasq.conf and /etc/systemd/system/dnsmasq.service daemon: (config files are located in 02_Config_Files)

*** START THE DNSMASQ DAEMON: Windows_Node and Data_Node should be issued a leased IP from dnsmasq and the proper squadron.local domain with an authoritative DNS of you configured server IP (e.g. 10.10.30.1 /domain: squadron.internal) ***

sudo systemctl daemon-reload
sudo systemctl enable --now dnsmasq
sudo systemctl status dnsmasq

INTERNAL RANGE NOTE + ADD dnsmasq.conf and dnsmasq.service will be added as seperate configuration files to the repo:
1. Lab_Internal Interface = eth0 (MAC: 0C-74-01) / 10.10.30.1 Network
   - Only Data_Node and Windows_Node should touch this network
2. Default Switch Interface = eth1 (MAC: 0C-74-02)

*** Enable IP Forwarding on the Data_Node and Windows_Node ***
1. ip -br addr
2. ip route show default (eth1 should be your WAN uplink)
3. Enable IP Forwarding:
   - Immediate: sudo sysctl -w net.ipv4.ip_forward=1
   - Persistent: echo 'net.ipv4.ip_forward = 1' | sudo tee /etc/sysctl.d/99-ipforward.conf
   - sudo sysctl --system
4. Confirm IP Forwarding id Enabled: sysctl net.ipv4.ip_forward (should read = 1)

*** Setup NAT + nftables Forwarding Rules on Infra_Node ***
1. Infra_Node uses nftables. Create following rules on the Infra_Node with the below nftables commands:
2. NAT table + masquerade lab traffic out the uplink
   - sudo nft add table ip nat
   - sudo nft add chain ip nat postrouting '{ type nat hook postrouting priority 100 ; }'
   - sudo nft add rule ip nat postrouting ip saddr 10.10.30.0/24 oif "eth1" masquerade
3. Filter table + forwarding bi-directional
   - sudo nft add table ip filter
   - sudo nft add chain ip filter forward '{ type filter hook forward priority 0 ; }'
   - sudo nft add rule ip filter forward iif "eth0" oif "eth1" accept
   - sudo nft add rule ip filter forward iif "eth1" oif "eth0" ct state related,established accept
4. Verify the rulesdet landed: sudo nft list ruleset
   - You should see the masquerade rule under postrouting and the two forward rules.
5. Test that you can ping 8.8.8.8 and google.com from both the Data_Node and Windows_Node BEFORE making the rules persistent.
6. If you can now route throgh the Infra_Node out to the internet, make the nft ruleset persistent:
   1. sudo sh -c 'nft list ruleset > /etc/nftables.conf'
   2. sudo systemctl enable --now nftables

*** PAUSE: CREATE NEW CHECKPOINTS IN HYPER-V FOR ALL VMS ***

# Task 1.4: Boot and SSH Hardening

*** Generate SSH key pair on Infra_Node and distribute to Data_Node ***
1. On Infra Node: ssh-keygen -t ed25519 -C "infra-node -> data-node" -f ~/.ssh/id_ed25519
2. ssh-copy-id -i ~/.ssh/id_ed25519.pub <user>@<data_node_ip>
3. SSH to Data_Node to test: ssh -i /home/sandbox_user/.ssh/id_ed25519 'sandbox_user@10.10.30.116 / Substitue your hostname and IP
4. Sanity Check (force no Password Authentication): ssh -o PasswordAuthentication=no -i /home/sandbox_user/.ssh/id_ed25519 'sandbox_user@10.10.30.116
5. If ssh access worked without password authentication, proceed to disable password authentication (CREATE CHECKPOINT ON DATA_NODE FIRST AS BACKUP PLAN!)

*** Disable password authentication on Data_Node ***
1. SSH to Data_Node
2. sudo nano /etc/ssh/sshd_config.d/10-hardening.conf (add following drop-in rules)
PasswordAuthentication no
ChallengeResponseAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
3. Test the configuration syntax: sudo sshd -t
4. Reload sshd: sudo systemctl reload sshd
5. Test that ssh key authentication still works (Step 3 in 'Generate SSH key pair' steps above)
6. Test that the door is closed: ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no <user>@data-node.squadron.internal (should receive permission denied message)

# Task 1.5: Authoritative Time

1. Install chrony: sudo apt install chrony
2. Configure /etc/chrony/chrony.conf
Add the following lines below "Use Debian vendor zone":
- *** Serve time to the internal network ***
allow 10.10.30.0/24
- *** Serve even if upstream is briefly unreachable ***
local stratum 10
3. sudo systemctl restart chrony
4. sudo systemctl enable chrony
5. chronyc sources -v
6. chronyc tracking
7. Advertise the time server via DHCP:
   - Add 'dhcp-option=option:ntp-server,10.10.30.1' to /etc/dnsmasq.conf
8. Test and reload dnsmasq: 
   - sudo /usr/local/sbin/dnsmasq --test
   - sudo systemctl restart dnsmasq
9. Block outbound NTP traffic from the internal network:
   - sudo nft insert rule ip filter forward iif "eth0" udp dport 123 drop
   - sudo nft insert rule ip filter forward iif "eth0" tcp dport 123 drop
   - NOTE: Use 'insert' instead of 'add' in nft command to ensure the firewall rule sits above the general iif port forwarding rules, or it won't trigger. Using add places the rule at the bottom of the chain.
10. Persist the changes: sudo sh -c 'nft list ruleset > /etc/nftables.conf'
11. SSH to Data_Node
12. Configure /etc/chrony.conf:
    - Comment out the NTP pool. It's not longer needed with the traffic being blocked at the firewall.
    - Add 'server 10.10.30.1 iburst' right below to point Data_Node to the gateway
13. Restart chronyd: sudo systemctl restart chronyd
14. Test Data_Node is now synced to the gateway:
    - chronyc sources -v
    - chronyc tracking

# Task 1.6: Storage and Persistence

1. Open PowerShell (create 4GB dynamic VHDX): New-VHD -Path "C:\<Hyper-V path>\Data_Node\ops_disk.vhdx" -SizeBytes 4GB -Dynamic
2. Attach to the Data_Node's SCSI controller: Add-VMHardDiskDrive -VMName "Data_Node" -Path "C:\Program Files\Hyper-V\Virtual Machines\Data_Node\ops_disk.vhdx"
3. Log into Data_Node to confirm that the new disk was created and attached:
   - lsblk
   - sudo dmesg | tail -20  # shows the newly attached disk
   - Note: Data_Node attached the new drive to 'sdb'
4. Partition into two equal partitions with 'parted' utility:
   - sudo parted /dev/sdb --script mklabel gpt
   - sudo parted /dev/sdb --script mkpart primary ext4 1MiB 2GiB
   - sudo parted /dev/sdb --script mkpart primary xfs 2GiB 100%
5. Verify the new layout: 'sudo parted /dev/sdb --script print && lsblk /dev/sub'. Two partitions should be seen: sdb1 and sdb2
6. Create the filesystems:
   - ext4 on the first partition: sudo mkfs.ext4 /dev/sdb1
   - xfs on the second partition: sudo mkfs.xfs /dev/sdb2
7. Get the UUIDs of each partition for /etc/fstab mounting: sudo blkid /dev/sdb1 /dev/sdb2 (save them in a txt document somewhere on data_node)
8. Create mount points and add them /etc/fstab by UUID:
- sudo mkdir -p /mnt/ops_data /mnt/log_data
- sudo nano /etc/fstab
- Add these two lines:
  - UUID=<sdb1 UUID>   /mnt/ops_data   ext4   defaults   0 2
  - UUID=<sdb2 UUID>   /mnt/log_data   xfs    defaults   0 2
  - NOTE: To see the clean UUIDs, run 'lsblk -o NAME, UUID,FSTYPE /dev/sdb
9. Test fstab before rebooting:
- sudo systemctl daemon-reload
- sudo mount -a
- lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT /dev/sdb
- findmnt --verify
- df -h /mnt/ops_data /mnt/log_data

# Task 1.7: Indentity and Special Permissions

*** Create the group ***
1. On Data_Node: sudo groupadd cyber_team

*** Create two users and add them to group ***
1. sudo useradd -m -G cyber_team alpha
2. sudo useradd -m -G cyber_team bravo
3. sudo passwd alpha
4. sudo passwd bravo
5. Confirm group memership: groups alpha / groups bravo / id alpha

*** Create new shared directory and assign it to group ***
1. sudo mkdir -p /mnt/ops_data/shared
2. sudo chgrp cyber_team /mnt/ops_data/shared

*** Apply the permissions and sticky bit + group write + SGID (new files inherit the group) ***
1. sudo chmod 2770 /mnt/ops_data/shared (SGID enabled with "2". Without SGID, when alpha creates a file it'd be group 'alpha' and bravo won't have access.)
2. Adding sticky bith with +1 to SGID (2): sudo chmod 3770 /mnt/ops_data/shared
3. Verify that that permissions applied correctly: ls -ld /mnt/ops_data/shared
   - Should see: drwxrws--T
  
# Task 1.8: Systemd Daemon & Windows Task Scheduler

*** Build Data_Node metics bash script ***
1. sudo nano /usr/local/bin/metrics-logger.sh
2. Created bash script dropped it into new repository folder "03_Scripts"
3. Make script executable: sudo chmod +x /usr/local/bin/metrics-logger.sh
4. Test the script before turning it into a daemon:
   - sudo /usr/local/bin/metrics-logger.sh &
   - sleep 65
   - tail /mnt/log_data/metrics.log
   - Should see 3-4 timestamed metrics lines

*** Create the metrics-logger daemon ***
1. sudo nano /etc/systemd/system/metrics-logger.service
2. Created service daemon /etc/systemd/system/metrics-logger.service and dropped it into new repository folder "03_Scripts"
3. Enable, start and watch new entries in /mnt/log_data/metrics.log
   - sudo systemctl daemon-reload
   - sudo systemctl enable --now metrics-logger.service
   - sudo systemctl status metrics-logger.service --no-pager
   - tail -f /mnt/log_data/metrics.log

*** Ensure that restart-on-death works ***
1. sudo systemctl status metrics-logger.service | grep PID
2. sudo kill <pid>
3. sleep 6
4. sudo systemctl status metrics-logger.service --no-pager   # should show running again, new PID
5. Should see that daemon is still active

*** Ensure that the daemon survives a Data_Node reboot
1. tail -1 /mnt/log_data/metrics.log
2. sudo reboot
3. After it comes back up:
   - tail -5 /mnt/log_data/metrics.log
   - systemctl is-enabled metrics-logger.service

*** Windows_Node: SSH client, key trust and scheduled pull***
1. Check to make sure OpenSSH client is installed on Windows_Node: Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Client*'
2. If the result is "Installed," proceed to next step. If the result is "NotPresent," run 'Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0'
3. Verify installation: ssh -V

*** Generate new key pair on Windows_Node ***
1. ssh-keygen -t ed25519 -C "windows-node -> data-node"
