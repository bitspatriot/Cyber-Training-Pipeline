*** Install Hyper-V via CLI ***

1. Launch an elevated command prompt
2. Command: dism.exe /Online /Enable-Feature /FeatureName:Microsoft-Hyper-V /All
3. Open elevated Powershell Window: Verify Hyper-V cmdlets are 	available: Get-Command -Module Hyper-V
4. List Existing Network Adapters: Get-NetAdapter | ft Name, Status
5. Create new Internal Switch: New-VMSwitch -name "Lab_Internal" -SwitchType Internal

*** Create three VMs via CLI (Powershell) ***

# 1. Define VM configuration parameters
$vmName = "MyHeadlessVM"
$memoryAmount = 4GB
$diskSize = 60GB
$path = "C:\Hyper-V\Virtual Machines"

# 2. Create the VM attached initially to the custom internal switch
New-VM -Name $vmName `
       -MemoryStartupBytes $memoryAmount `
       -NewVHDPath "$path\$vmName\$vmName.vhdx" `
       -NewVHDSizeBytes $diskSize `
       -SwitchName "Lab_Internal" `
       -Generation 2

*** IMPORTANT: Windows Server requires a Generation 1 to bootstrap the image. Generation 2 can be used for the Debian/Linux VMs. If you create the Windows VM as Generation 2, you'll have to recreate it. ***

# 3. Add the second network interface for the Hyper-V Default Switch
Add-VMNetworkAdapter -VMName $vmName -SwitchName "Default Switch"

# 4. Optional: Enable Automatic Checkpoints / Set CPU cores
Set-VMProcessor -VMName $vmName -Count 2

# 5. Start the VM headless (in the background, without launching Hyper-V Manager GUI)
Note: Start downloading all three ISOs prior to disabling the adapter.

1. Add DVD Drive and Mount ISO to the VM

Debian and Rocky VMs/Nodes
- Add-VMDvdDrive -VMName "Infra_Node" -Path "C:\ISOs\[ISO filename]" -Passthru | ForEach-Object { Set-VMFirmware -VMName $_.VMName -SecureBootTemplate "MicrosoftUEFICertificateAuthority" -FirstBootDevice $_ }

Windows Server VM/Node
- Add-VMDvdDrive -VMName "Windows_Node" -Path "C:\ISOs\[ISO filename]" -Passthru | ForEach-Object { Set-VMFirmware -VMName $_.VMName -SecureBootTemplate "MicrosoftWindows" -FirstBootDevice $_ }

2. Start the VM via CLI: Start-VM -Name $vmName

*** Infra_Node Preparation for DHCP/DNS (Task 1.3) ***

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

# 6.Bind static IP address to eth1

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

# 7. Build dnsmasq from source
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

# 9. Enable IP Forwarding on the Data_Node and Windows_Node
1. ip -br addr
2. ip route show default (eth1 should be your WAN uplink)
3. Enable IP Forwarding:
   - Immediate: sudo sysctl -w net.ipv4.ip_forward=1
   - Persistent: echo 'net.ipv4.ip_forward = 1' | sudo tee /etc/sysctl.d/99-ipforward.conf
   - sudo sysctl --system
4. Confirm IP Forwarding id Enabled: sysctl net.ipv4.ip_forward (should read = 1)

# 10. Setup NAT + nftables Forwarding Rules on Infra_Node
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

