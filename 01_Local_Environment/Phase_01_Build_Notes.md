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
5. Create and configure the /etc/dnsmasq.conf and /etc/systemd/system/dnsmasq.service daemon:

*** dnsmasq.conf ***

# --- Interface binding ---
interface=eth1
bind-interfaces
listen-address=10.10.0.1
# never touch the external/other interfaces
except-interface=lo

# --- DNS ---
# act as the resolver for the internal net
domain-needed
bogus-priv
no-resolv
server=1.1.1.1        # upstream forwarders for anything non-local
server=9.9.9.9
domain=squadron.internal
local=/squadron.internal/  # local domain, answered authoritatively
domain=internal.lan
expand-hosts

# --- DHCP ---
dhcp-range=10.10.0.100,10.10.0.200,255.255.255.0,12h
dhcp-option=option:router,10.10.0.1       # gateway = this node
dhcp-option=option:dns-server,10.10.0.1   # clients use us for DNS
dhcp-authoritative

# --- logging (useful while validating) ---
log-queries
log-dhcp

*** END - ALWAYS test you dnsmasq.conf file for syntax error with 'sudo /usr/local/sbin/dnsmasq --test' command ***

*** dnsmasq.service ***

[Unit]
Description=dnsmasq (compiled from source)
After=network-online.target
Wants=network-online.target

[Service]
ExecStartPre=/usr/local/sbin/dnsmasq --test
ExecStart=/usr/local/sbin/dnsmasq -k --conf-file=/etc/dnsmasq.conf
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure

[Install]
WantedBy=multi-user.target

*** END ***

*** START THE DNSMASQ DAEMON: Windows_Node and Data_Node should be issued a leased IP from dnsmasq and the proper squadron.local domain with an authoritative DNS of you configured server IP (e.g. 10.10.30.1 /domain: squadron.internal) ***

sudo systemctl daemon-reload
sudo systemctl enable --now dnsmasq
sudo systemctl status dnsmasq

INTERNAL RANGE NOTE + ADD dnsmasq.conf and dnsmasq.service will be added as seperate configuration files to the repo:
1. Lab_Internal Interface = eth0 (MAC: 0C-74-01) / 10.10.30.1 Network
   - Only Data_Node and Windows_Node should touch this network
2. Default Switch Interface = eth1 (MAC: 0C-74-02)

# 9. 

