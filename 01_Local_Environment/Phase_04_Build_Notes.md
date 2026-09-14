# Task 4.1: Plumbing and Segmentation

*** Unpack the pfSense Image ***
1. From Powershell on the Host running Hyper-V: Invoke-WebRequest -Uri "https://atxfiles.netgate.com/mirror/downloads/pfSense-CE-2.7.2-RELEASE-amd64.iso.gz" -OutFile pfSense.iso.gz
2. Install 7-Zip on Host: winget install --id 7zip.7zip -e --source winget
3. Unpack the pfSense .gz ISO: & "C:\Program Files\7-Zip\7z.exe" e pfSense.iso.gz
4. Verify you have the real pfSense ISO and not a truncated download: $env:USERPROFILE\Downloads\pfSense-CE-2.7.2-RELEASE-amd64.iso | Select-Object Name, Length
   - ISO filesize should be several hundred MBs

*** Create the pfSense VM (two adapters) ***
IMPORTANT NOTE: Make the pfSense a Generation 1 VM

In Powershell (Administrator privileges):
$vmName   = "pfSense"
$vhdPath = "C:\Program Files\Hyper-V\Virtual Machines\pfsense\pfSense.vhdx"
$isoPath = "$env:USERPROFILE\Downloads\pfSense-CE-2.7.2-RELEASE-amd64.iso"

New-VM -Name $vmName -Generation 1 -MemoryStartupBytes 2GB -NewVHDPath $vhdPath -NewVHDSizeBytes 20GB
Set-VMMemory $vmName -DynamicMemoryEnabled $false (don't use dynamic memory for a firewall)

*** Attach the install ISO ***
Set-VMDvdDrive -VMName $vmName -Path $isoPath

*** Create two network adapters ***
1. Adapter 1 (WAN, connected to the Default Switch (path to internet)): Connect-VMNetworkAdapter -VMName $vmName -Name "Network Adapter" -SwitchName "Default Switch"
2. Adapter 2 (LAN trunk on Lab_Internal switch (carries all three VLANS)): Add-VMNetworkAdapter -VMName $vmName -Name "LAN-Trunk" -SwitchName "Lab_Internal"

*** Start the pfSense VM and capture MAC Addresses ***
1. Start-VM $vmName
2. Start-Sleep -Seconds 3
3. Get-VMNetworkAdapter -VMName $vmName | Select-Object Name, SwitchName, MacAddress
4. Important for pfSense configuration (Record MAC Addresses):
   - Network Adapter (WAN Default Switch)     00:15:5D:0C:74:06
   - LAN-Trunk (Lab_Internal)                 00:15:5D:0C:74:07
5. Turn off the pfSense: Stop-VM: 
6. Set pfSense MACs to static so they don't change on recreation:
   - Set-VMNetworkAdapter -VMName $vmName -Name "Network Adapter"        -StaticMacAddress "00155D0C7406"
   - Set-VMNetworkAdapter -VMName $vmName -Name "LAN-Trunk" -StaticMacAddress "00155D0C7407"

*** Preperation steps before running the pfSense installer ***
1. Disable checksum offloading on both adapters:
   *** Disable all the offload features that cause issues on Hyper-V ***
   - Set-VMNetworkAdapter -VMName $vmName -IpsecOffloadMaximumSecurityAssociation 0
   *** Disable checksum/VMQ offloads for both adapters ***
   - Get-VMNetworkAdapter -VMName $vmName | ForEach-Object {
    Set-VMNetworkAdapter -VMName $vmName -Name $_.Name -DhcpGuard Off -RouterGuard Off
    }
    - NOTE: There will be another setting inside the pfSense console where this needs to be configured (disabled) after the install.
2. Configure the VLAN trunk on the LAN adapter (trunk mode carrying all three VMs):
   - Set-VMNetworkAdapterVlan -VMName $vmName -VMNetworkAdapterName "LAN-Trunk" -Trunk -AllowedVlanIdList "10,20,40" -NativeVlanId 99
3. Verify the trunk configuration took: Get-VMNetworkAdapterVlan -VMName $vmName
   - see the LAN-Trunk adapter in Trunk mode with allowed VLANs 10,20,40 and native 99, and the WAN adapter in Untagged.

*** Install pfSense ***
1. $vmName = "pfSense" (just in case your variable has been unset)
2. Boot the pfSense (Powershell): Start-VM -VMName $vmName
3. Choose "Install pfSense" (Ensure selection of UFS. Not ZFS)
4. Accept default selection of full usage and default partitioning
5. Allow the install to complete
6. Before hitting reboot, unmount the ISO from the Hyper-V VM:
   - Set-VMDvdDrive -VMName "pfSense" -Path $null
7. Select "Reboot" and allow the pfSense to restart
8. Select "n" for VLAN setup
9. Enter the WAN interface name: Enter 'hn0' (make sure the MAC address listed a few lines up is correct for that interface)
10. Enter the WAN interface name: Enter 'hn1' (make sure the MAC address listed a few lines up is correct for that interface)

# Task 4.2: The Handoff

*** Use Data_Node as a temporary management VM for the pfSense GUI (Reason: VLAN20 doesn't exist yet until we get pfSense console access) ***
NOTE: If RDP'ing remotely through Tailscale, don't change your Hotst IP to the pfSense LAN (192.x) IP. Risk of dropping RDP connection, which is why you should use the Data_Note (e.g. linux makes it easy to set a temporary static IP and browse with curl.)
1. On Host (Powershell): Set-VMNetworkAdapterVlan -VMName "Data_Node" -Access -VlanId 20
2. On Data_Node:
   - sudo ip addr add 192.168.1.50/24 dev eth0
   - sudo ip route add default via 192.168.1.1
3. On Host (Powershell): for the Data-Node on VLAN20-access to reach pfSense's untagged LAN, the trunk's native VLAN must be 20 so pfSense treats VLAN20 frames as the untagged LAN. Set that temporarily:
   - Set-VMNetworkAdapterVlan -VMName "pfSense" -VMNetworkAdapterName "LAN-Trunk" -Trunk -AllowedVlanIdList "10,20,40" -NativeVlanId 20
4. On Data_Node (test untagged traffic to LAN interface): ping -c3 192.168.1.1

*** Access pfSense GUI from Data_Node ***
1. Open web browser (Firefox already installed)
2. Navigate to https://192.168.1.1
3. Login into the pfSense:
   - Default Username: admin
   - Default Password: pfsense
4. Navigate to Interfaces -> Assignments -> VLANS tab -> Add
   - For all VLANS, the parent interface is the LAN trunk (hn1)
        VLAN Tag	Parent	Description
        10	         hn1	Users
        20	         hn1	Servers
        40	         hn1	DMZ
5. Navigate to Interfaces -> Assigments
6. Change "LAN" dropdown to "VLAN 20 on hn1"
7. Add "hn1.10" -> it becomes OPT1 (rename to VLAN10/Users)
8. Add "hn1.40" -> it becomes OPT2 (rename to VLAN30/DMZ)
   - If you save the config, you'll lose access to the pfSense GUI
   - Open the pfSense console (no GUI needed to regain access)
     - Choose option 2 — Set interface(s) IP address.
     - Select LAN.
     - It'll ask to configure IPv4 via DHCP → answer n (no).
     - Enter the LAN IPv4 address: 10.10.20.1
     - Subnet bit count: 24
     - Gateway for LAN: press Enter (none — LAN is not upstream).
     - IPv6 → n or skip.
     - "Enable DHCP server on LAN?" → n (VLAN20 gets no DHCP).
     - It'll ask about reverting to HTTP for the webConfigurator — you can say n (keep HTTPS) or y; either works for access.
9. Re-address the Data_Node (eth0) interface to match the new VLAN20 subnet:
    - sudo ip addr flush dev eth0
    - sudo ip addr add 10.10.20.20/24 dev eth0
    - sudo ip route add default via 10.10.20.1
    - IMPORTANT NOTE/PITFALL: gotcha: re-running Set-VMNetworkAdapterVlan with -NativeVlanId while a trunk already exists can append rather than replace, producing a duplicate/corrupted VLAN in the allowed list that silently breaks that VLAN's delivery — reset with -Untagged first, then re-apply the full trunk in one command.
10. Log back into the pfSense at https://10.10.20.1
11. Select Interfaces -> OPT1
12. Check box "Enable interface"
13. Change 'Description': VLAN10Users
14. Change 'IPv4 Configuration Type': Static IPv4
15. Change 'IPv4 Address': 10.10.10.1/24
16. Click "Save"
17. Select Interfaces -> OPT2
18. Check box "Enable interface"
19. Change 'Description': VLAN10Users
20. Change 'IPv4 Configuration Type': Static IPv4
21. Change 'IPv4 Address': 10.10.40.1/24
22. Click "Save"

*** DHCP on VLAN10 (Users) only ***
1. Select "Services"
2. Select DHCP Server
3. Select "VLAN10Users" tab
4. Check "Enable DHCP server on VLAN10Users interface"
5. Set the DNS server to 10.10.20.10 (Future looking: the Windows DC doesn't exist yet, but it will)
6. Set the Gateway to 10.10.10.1
7. Save the configuration
8. Confirm that the LAN (VLAN20) and DMZ (VLAN30) have no DHCP configured

*** Configure firewall rule for VLAN10 (Users) ***
1. Navigate to Firewall -> Aliases
2. Click 'Add'
3. Alias Name: mgmt_ports
4. Description: Management Ports
5. Type: Port(s)
6. Add port 22 / Description: SSH
7. Add port 3389 / Description: RDP
8. Save the Alias
9. Navigate to Firewall -> Rules
10. Select "VLAN10Users" tab
11. Click 'Add' to build the rule
    - Action: Block (or Reject)
    - Protocol: TCP
    - Source: OPT1 net (VLAN10 subnet)
    - Destination: LAN net (VLAN20 subnet)
    - Desitnation Port Range (From): Other
    - Custom: Begin typing 'mgmt' to see your newly created alias
    - To: Leave "other"
    - Save the rule

*** Configure firewall rule for VLAN10 (Users) -> VLAN20 (LAN) for other services ***
Navigate to Firewall -> Rules
1. Select "VLAN10Users" tab
2. Click 'Add' to build the rule
    - Action: Pass
    - Protocol: TCP/UDP
    - Source: OPT1 net (VLAN10 subnet)
    - Destination: LAN net (VLAN20 subnet)
    - Desitnation Port Range (From): DNS (53)
    - To: DNS (53)
    - Save the rule

*** Configure firewall rule for VLAN10 (Users) -> Internet ***
Navigate to Firewall -> Rules
1. Select "VLAN10Users" tab
2. Click 'Add' to build the rule
    - Action: Pass
    - Protocol: TCP/UDP
    - Source: OPT1 net (VLAN10 subnet)
    - Destination: Any
    - Desitnation Port Range (From): Any
    - To: Any
    - Save the rule

IMPORTANT NOTE: The block rule must sit above the allow-any rule, or the allow matches first and the block never fires.

*** Migrate Windows_Node to VLAN20 ***
1. Run ncpa.cpl
2. Right click on Ethernet interface and select 'Properties'
3. Highlight 'Internet Protocol Version 4 (TCP/IPv4)'
4. IP Addres: 10.10.20.10
5. Subnet Mask: 255.255.255.0
6. Default Gateway: 10.10.20.1
7. Preferred DNS: 10.10.20.30 (Temporary. This IP will flip to 127.0.0.1 during DC promotion)
8. Click 'OK'
9. Retag the adapter on Hyper-V host (Powershell): Set-VMNetworkAdapterVlan -VMName "Windows_Node" -Access -VlanId 20
10. From Windows_Node (Verify connectivity):
    - Confirm new network changes: ipconfig /all
    - Test-Connection 10.10.20.1 -Count 3
    - Test-Connection 8.8.8.8 -Count 3
    - ping 10.20.20.1
    - ping 8.8.8.8

# Task 4.3: Identity and Directory Services

*** Promote Windows_Node to DC (new forest) from Powershell ***
NOTE: Make sure you know the SQUADRON\Administrator password. Once promotion is complete, you previous user (e.g. sandbox_user) will no longer be able to log in locally because the Windows_Node is now a domain joined DC. Login as Administrator after the reboot and user account to "Domain Admins": Add-ADGroupMember -Identity "Domain Admins" -Members "<username>"
1. Set-DnsClientServerAddress -InterfaceAlias "Ethernet" -ServerAddresses 127.0.0.1,8.8.8.8
2. Install-WindowsFeature AD-Domain-Services -IncludeManagementTools
3. Install-ADDSForest `
  -DomainName "squadron.internal" `
  -DomainNetbiosName "SQUADRON" `
  -InstallDns `
  -ForestMode "WinThreshold" `
  -DomainMode "WinThreshold" `
  -SafeModeAdministratorPassword (Read-Host -AsSecureString "DSRM password") `
  -Force

*** Verify the promotion suceeded ***
1. Confirm AD/DS is running and the domain is right:
   - Get-ADDomain | Select-Object DNSRoot, NetBIOSName, DomainMode
   - Get-ADDomainController | Select-Object Name, Domain, IPv4Addres
2. Confirm the DNS forward zone was created:
   - Get-DnsServerZone | Select-Object ZoneName, ZoneType, IsReverseLookupZone
3. Should see: 
   - DNSRoot: squadron.internal, 
   - DC named as itself at 10.10.20.10
   - Forward zone squadron.internal present

*** Point the DC's own DNS to point only at itself ***
1. Set-DnsClientServerAddress -InterfaceAlias "Ethernet" -ServerAddresses 127.0.0.1

*** Configure the DNS forwarder so the DC resolves public names ***
NOTE: Set WAN interface to static 172.x address and 172.x Default Switch gateway if DCHP lease doesn't renew.
1. Set-DnsServerForwarder -IPAddress 8.8.8.8, 1.1.1.1
2. Test that the DC now resolved both internal and external DNS names:
   - Internal: Resolve-DnsName squadron.internal
   - External: Resolve-DnsName google.com

*** Configure reverse lookup zone and register the Linux hosts ***
1. Add-DnsServerPrimaryZone -NetworkID "10.10.20.0/24" -ReplicationScope "Forest"
2. Add-DnsServerResourceRecordA -ZoneName "squadron.internal" -Name "data-node"  -IPv4Address "10.10.20.20" -CreatePtr
3. Add-DnsServerResourceRecordA -ZoneName "squadron.internal" -Name "infra-node" -IPv4Address "10.10.20.30" -CreatePtr
4. Verify:
   - Resolve-DnsName data-node.squadron.internal
   - Resolve-DnsName 10.10.20.20
   - Resolve-DnsName infra-node.squadron.internal
   - Resolve-DnsName 10.10.20.30

*** Disable Hyper-V time integration ***
1. On Host (Powershell): Disable-VMIntegrationService -VMName "Windows_Node" -Name "Time Synchronization"
2. Confirm (on Host): Get-VMIntegrationService -VMName "Windows_Node" -Name "Time Synchronization"
   - Should show Enabled: False
   - If not, restart the Windows Time service (on Windows_Node (New DC)):
     - Restart-Service w32time
     - w32tm /query /source
     - Should 'Local CMOS Clock' and not 'VM IC Time Synchronization Provider'

*** PAUSE: SNAPSHOT ALL VMS BEFORE PROCEDING TO INFRA_NODE MIGRATION. THE FOLLOWING STEPS CAN CAUSE LOCKOUTS OR DROPPED CONNECTIONS IF DONE INCORRECTLY OR OUT OF ORDER ***

1. Checkpoint-VM -Name pfSense -SnapshotName "pre-4.2-migration"
2. Checkpoint-VM -Name Windows_Node -SnapshotName "pre-4.2-migration"
3. Checkpoint-VM -Name Data_Node -SnapshotName "pre-4.2-migration"
4. Checkpoint-VM -Name Infra_Node -SnapshotName "pre-4.2-migration"

*** Build new bastion path on the pfSense (BEFORE migrating the Infra_Node) ***
1. On pfSense (GUI): Interfaces -> WAN -> Uncheck 'Block private networks and loopback addresses'
2. Click Save and Apply

*** NAT port-forward: WAN -> Infra-Node SSH ***
1. Firewall → NAT → Port Forward → Add:
   - Interface: WAN
   - Protocol: TCP
   - Destination: WAN address
   - Destination port range: from 2222 to 2222 (a custom external port — avoids clashing with pfSense's own SSH)
   - Redirect target IP: 10.10.20.30 (Infra-Node's future VLAN20 address)
   - Redirect target port: 22 (from the "Other" option, type 22)
   - Check "Add associated filter rule" (auto-creates the matching WAN pass rule)
   - Save → Apply.
   - Confirm associated WAN firewall rule exists:
     - Firewall → Rules → WAN → you should see a rule allowing TCP to 10.10.20.30:22 (created by the checkbox above)

*** Migrate Infra_Node to VLAN20 ***
1. From Host (Powershell): Get the correct adapter name: Get-VMNetworkAdapter -VMName "Infra_Node" | Select-Object Name, SwitchName, MacAddress
2. Both adapters are named "Network Adapter," so rename them first, so it's obvious which interface to move to VLAN20:
   - Get-VMNetworkAdapter -VMName "Infra_Node" |
    Where-Object SwitchName -eq "Lab_Internal" |
    Rename-VMNetworkAdapter -NewName "LAN-VLAN20"
   - Get-VMNetworkAdapter -VMName "Infra_Node" |
    Where-Object SwitchName -eq "Default Switch" |
    Rename-VMNetworkAdapter -NewName "WAN-Temp"
3. Verify change: Get-VMNetworkAdapter -VMName "Infra_Node" | Select-Object Name, SwitchName, MacAddress
4. Should now see two adapters named "LAN-VLAN20" and "WAN-Temp"
5. Tag the 'Lab_Internal' adapter: Set-VMNetworkAdapterVlan -VMName "Infra_Node" -VMNetworkAdapterName "LAN-VLAN20" -Access -VlanId 20
6. Verify it took: Get-VMNetworkAdapterVlan -VMName "Infra_Node"
7. ping -c3 10.10.20.1
8. ping -c3 10.10.20.10
9. Confirm the Infra_Node is litening and reachable on 10.10.30.30:22: sudo ss -tlnp | grep :22

*** Test the new bastion bath from the Host ***
1. ssh -p 2222 <infra-user>@172.29.208.50
   - Should get the dropped into the Indra_Node shell
   - The pfSense is forwarding SSH traffic to the Infra_Node through it's port-forwarding rule.
   - This test confirms that the Infra_Node's second adapter isn't accepting NAT SSH traffic on the depricated second network adapter.
2. Second confirmation (disable (don't delete) Infra_Nodes eth1 adapter and retest the connection through the pfSense)
   - On Host: Disconnect-VMNetworkAdapter -VMName "Infra_Node" -Name "WAN-Temp"
   - ssh -p 2222 <infra-user>@172.29.208.50

*** Remove the second adapter and retire the Phase 1 NAT ***
1. Remove-VMNetworkAdapter -VMName "Infra_Node" -Name "WAN-Temp"
2. Confirm the VLAN20 adapter remains: Get-VMNetworkAdapter -VMName "Infra_Node" | Select-Object Name, SwitchName, MacAddress
   - Should see only one remaining LAN-VLAN20 on Lab_Internal adapter
3. SSH from the host to Infra_Node: ssh -p 2222 <infra-user>@172.29.208.50
4. ip route (should only see default route via 10.10.20.1 (pfSense))

*** Retire Phase 1 NAT/forwarding (on Infra_Node) ***
1. Flush and siable Phase 1 nftables NAT ruleset:
   - sudo nft flush ruleset
   - sudo systemctl disable --now nftables
2. Turn off IP forwaring (pfSense routes now):
   - sudo sysctl -w net.ipv4.ip_forward=0
   - sudo rm -f /etc/sysctl.d/99-ipforward.conf
   - sudo sysctl --system
3. Verify Infra_Node still works after everything removed:
   - From Host: ssh -p 2222 <infra-user>@172.29.208.50
   - From Infra_Node:
     - ip route
     - ping -c3 10.10.20.1
     - ping -c3 8.8.8.8

*** Retire dnsmasq (DHCP + DNS) and repoint resolvers ***
1. sudo systemctl disable --now dnsmasq
2. Confirm it's gone: sudo ss -ulpn | grep -E ':53|:67' || echo "dnsmasq no longer listening"
3. sudo systemctl restart systemd-networkd
4. Infra_Node needs a the new resolver configured in /etc/resolve.conf:
   - sudo tee /etc/resolv.conf >/dev/null <<'EOF'
     nameserver 10.10.20.10
     search squadron.internal
     EOF
5. Test nslookup(s):
   - nslookup squadron.internal
   - nslookup google.com

*** Verify the Data_Node resolves to the new DC (Windows_Node) ***
1. On Data_Node:
   - cat /etc/resolv.conf
   - nmcli device show eth0 | grep IP4.DNS (will still show old Phase 1 Infra_Node resolver 10.10.30.1)
   - Set new DNS resolver:
     - sudo nmcli connection modify 93d37765-6240-4947-8af3-1da21468eea8 \
    ipv4.dns "10.10.20.10" \
    ipv4.ignore-auto-dns yes
   - sudo nmcli connection down  93d37765-6240-4947-8af3-1da21468eea8 && \ sudo nmcli connection up 93d37765-6240-4947-8af3-1da21468eea8
   - sudo nmcli connection up  93d37765-6240-4947-8af3-1da21468eea8 && \ sudo nmcli connection up 93d37765-6240-4947-8af3-1da21468eea8
   - nmcli device show eth0 | grep IP4.DNS
   - cat /etc/resolv.conf
   - nslookup squadron.internal
   - nslookup google.com

*** NTP handoff: Fix chrony's ACL on the Infra-Node ***
1. grep -E '^allow' /etc/chrony/chrony.conf
2. sudo sed -i 's|allow 10.10.30.0/24|allow 10.10.20.0/24|' /etc/chrony/chrony.conf
3. grep -E '^allow' /etc/chrony/chrony.conf
4. sudo systemctl restart chrony
5. Confirm Infra_Node is still syncing upstream:
   - chronyc sources -v
   - chronyc tracking

*** Point the Windows_Node (DC) at the Infra_Node for time ***
1. w32tm /config /manualpeerlist:"10.10.20.30" /syncfromflags:manual /reliable:yes /update
2. Restart-Service w32time
3. w32tm /resync
4. w32tm /query /source

*** Rebuild the outbound-NTP block on pfSense with the Infra_Node exemption ***
1. pfSense Rule 1 (LAN/VLAN20):
   - Interface: LAN
   - Action: Pass
   - Protocol: UDP
   - Source: 10.10.20.30 (Infra-Node, single host)
   - Destination: any
   - Destination port: 123
   - Description: "Allow Infra-Node NTP upstream (time source exemption)"
2. pfSense Rule 2 (LAN/VLAN20):
   - Interface: LAN
   - Action: Block
   - Protocol: UDP
   - Source: LAN net
   - Destination: any
   - Destination port: 123
   - Description: "Block internal outbound NTP"
3. pfSense Rule 3 (OPT1/VLAN10):
   - Interface: LAN
   - Action: Block
   - Protocol: UDP
   - Source: LAN net
   - Destination: any
   - Destination port: 123
   - Description: "Block internal outbound NTP"
4. Test the Infra_Node expemption and the other nodes block:
   - On Infra_Node: chronyc sources -v
     - Should still shows ^* upstream — the PASS rule let it through
   - On Data_Node: sudo chronyd -Q -t 5 'server pool.ntp.org iburst' 2>&1
     - Should timeout with 'Timeout reached. chronyd exiting'
     - DC should take time from the Infra_Node: w32tm /query /source (should show 10.10.20.30)

*** Repoint the Windows_Node scheduled task ***
1. Edit C:\ProgramData\LabOps\pull-metrics.ps1
2. Change $target line to "data-node.squadron.internal"
3. Start-ScheduledTask -TaskName "LabOps-PullMetrics"
4. Start-Sleep 10
5. Get-Content C:\ProgramData\LabOps\metrics.log -Tail 5

# Task 4.4: The Endpoint

*** Create new Windows 11 Enpoint VM (Gen 2) with TPM enabled ***
1. Download Windows 11 ISO from: https://www.microsoft.com/software-download/windows11
2. On Host (Powershell):
   - $vmName  = "Win11-Endpoint"
   - $vhdPath = "C:\Hyper-V\Win11-Endpoint\Win11.vhdx"
   - $isoPath = "C:\path\to\Win11.iso"
   - New-VM -Name $vmName -Generation 2 -MemoryStartupBytes 4GB -NewVHDPath $vhdPath -NewVHDSizeBytes 64GB
   - Set-VMProcessor -VMName $vmName -Count 2
   - Set-VMMemory -VMName $vmName -DynamicMemoryEnabled $false
   - Add-VMDvdDrive -VMName $vmName -Path $isoPath
   - $dvd = Get-VMDvdDrive -VMName $vmName
   - Set-VMFirmware -VMName $vmName -FirstBootDevice $dvd
   - Set-VMKeyProtector -VMName $vmName -NewLocalKeyProtector
   - Enable-VMTPM -VMName $vmName
   - Set-VMFirmware -VMName $vmName -EnableSecureBoot On -SecureBootTemplate "MicrosoftWindows"
3. Verify TPM and Secure Boot are set on new Win11 VM:
   - Get-VMSecurity -VMName $vmName
   - Get-VMFirmware -VMName $vmName | Select-Object SecureBoot, SecureBootTemplate

*** Attach the network adapter on the trunk tagged to VLAN10 ***
1. Connect-VMNetworkAdapter -VMName $vmName -SwitchName "Lab_Internal"
2. Set-VMNetworkAdapterVlan -VMName $vmName -Access -VlanId 10
3. Get-VMNetworkAdapterVlan -VMName $vmName

*** Install Windows 11 Pro ***
1. Host Powershell: Start-VM -VMName $vmName
2. Hit space bar within 2 seconds of VM boot to start Windows install
3. Select the defaults to complete the install
4. Once complete, verify the network (Powrshell):
   - ipconfig /all
   - IPv4 in 10.10.10.100–200
   - Default Gateway 10.10.10.1
   - DNS Servers 10.10.20.10
   - DHCP Server 10.10.10.1
5. Verify the connection:
   - Test-Connection 10.10.10.1 -Count 2 X
   - Test-Connection 10.10.20.10 -Count 2 X
   - Resolve-DnsName squadron.internal ✓
   - Resolve-DnsName google.com ✓
   - nslookup -type=SRV _ldap._tcp.dc._msdcs.squadron.internal ✓  

*** Check the clock before joining (Powershell) ***
1. On Windows_Node (DC): Get-Date
2. On WIN11-ENDPOINT (DC): Get-Date
NOTE: It's important to make sure the times match to avoid kerboros issues. Tif the timezones are different on each node, run: Set-TimeZone -Id "Eastern Standard Time" on both.

*** Join WIN11-ENDPOINT to the domain ***
1. Add-Computer -DomainName "squadron.internal" -Credential (Get-Credential) -Restart
2. Login with Windows_Node domain administrator account:
   - Username: SQUADRON\Administrator
   - Password: Administrator password
3. After reboot, verify domain membership: (Get-WmiObject Win32_ComputerSystem).Domain
   - Should read squadron.internal

*** Disjoin WIN11-ENDPOINT from Hyper-V time now that it's joined to domain ***
1. On host: Disable-VMIntegrationService -VMName "Win11-Endpoint" -Name "Time Synchronization"
2. One the Win11-Endpoint:
   - w32tm /resync
   - w32tm /query /source
   - Should show Windows_Node (DC) hostname

*** Install Remote Server Administrator Tools (RSAT) on Win11-Endpoint ***
1. Get-WindowsCapability -Online -Name "Rsat*" | Select-Object Name, State
2. Add-WindowsCapability -Online -Name "Rsat.ActiveDirectory.DS-LDS.Tools~~~~0.0.1.0"
3. Add-WindowsCapability -Online -Name "Rsat.GroupPolicy.Management.Tools~~~~0.0.1.0"
4. Verify the installation: Get-WindowsCapability -Online -Name "Rsat*" | Where-Object State -eq "Installed"
5. Take note of Windows_Name (DC) hostname: WIN-SLBA0U0E53P
6. Confirm all the domain tools that are needed to continue exist: Get-Command dsa.msc, gpmc.msc -ErrorAction SilentlyContinue

*** Create the AD objects and share ***
1. New-ADOrganizationalUnit -Name "Workstations" -Path "DC=squadron,DC=internal" -ProtectedFromAccidentalDeletion $true
2. Get-ADOrganizationalUnit -Filter 'Name -eq "Workstations"' | Select-Object Name, DistinguishedName
3. Get-ADComputer -Filter 'Name -like "*"' | Select-Object Name, DistinguishedName
4. Get-ADComputer -Identity "<Win11-computer-name>" |
    Move-ADObject -TargetPath "OU=Workstations,DC=squadron,DC=internal"
5. Get-ADComputer -Identity "<Win11-computer-name>" | Select-Object Name, DistinguishedName

*** Create the Operators security group and add member ***
1. New-ADGroup -Name "Operators" -GroupScope Global -GroupCategory Security `
    -Path "DC=squadron,DC=internal" `
    -Description "Operators — drive map + fine-grained password policy scope"
2. Verify: Get-ADGroup -Identity "Operators" | Select-Object Name, GroupScope, DistinguishedName
3. Add-ADGroupMember -Identity "Operators" -Members "sandbox_user"

*** Create the file share on the DC ***
1. New-Item -Path "C:\Shares\OperatorsData" -ItemType Directory -Force
2. New-SmbShare -Name "OperatorsData" -Path "C:\Shares\OperatorsData" -FullAccess "SQUADRON\Domain Admins" -ChangeAccess "SQUADRON\Operators" 
   - NOTE: This shares C:\Shares\OperatorsData as \\<DC-hostname>\OperatorsData, giving the Operators group Change (read/write) access at the share level.
     - Windows_Node (DC) Hostname: WIN-SLBA0U0E53P
3. Set NTFS persmissions to match (share + NTFS both gate access)
   - $acl = Get-Acl "C:\Shares\OperatorsData"
   - $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    "SQUADRON\Operators","Modify","ContainerInherit,ObjectInherit","None","Allow")
   - $acl.SetAccessRule($rule)
   - Set-Acl "C:\Shares\OperatorsData" $acl
4. Verify:
   - On Windows_Node:
     - Get-SmbShare -Name "OperatorsData"
     - Get-SmbShareAccess -Name "OperatorsData"
   - On Win11-Endpoint:
     - Test-Path "\\WIN-SLBA0U0E53P\OperatorsData" (Should return "True")

*** NOTE: Best practice is to rename the DC to a more readable hostname (e.g. DC01), instead of the default auto-generated one created by Windows. Because the DC has already been promoted, there's more involved than simply 'Rename-Computer', so proceedning without the rename. For future builds that aren't a lab environment, recommend renaming the DC as soon as the Windows Server install is completed

*** Create and link the drive-map GPO ***
NOTE: Ensure your logged in as SQUADRON\<username> and not as local user. Freating the GPO will fail otherwise

1. New-GPO -Name "GPP - Map OperatorsData Drive" -Comment "Maps M: to \\WIN-SLBA0U0E53P\OperatorsData for Operators; loopback merge"
2. New-GPLink -Name "GPP - Map OperatorsData Drive" -Target "OU=Workstations,DC=squadron,DC=internal"
3. On Win11_Endpoint:
   -    Group Policy Management
     └ Forest: squadron.internal
        └ Domains
           └ squadron.internal
              └ Workstations                          ← your OU
                 └ GPP - Map OperatorsData Drive      ← your GPO (linked here)
4. Right click "GPP - Map OperatorsData Drive" -> Edit
   - This opens the Group Policy Management Editor in a new window
5. Navigate to lopback setting:
   - Computer Configuration
  └ Policies
     └ Administrative Templates
        └ System
           └ Group Policy
6. Double-click "Configure user Group Policy loopback processing mode"
   - Select the "Enabled" radio button
   - Options: Select "Merge"
   - Click "OK"
7. From the same "Group Policy Management Editor":
   - User Configuration
  └ Preferences
     └ Windows Settings
        └ Drive Maps
8. Right-click "Drive Maps":
   - On the General tab:
     - Action: Update
     - Location: \\WIN-SLBA0U0E53P\OperatorsData
     - Reconnect: ✅ checked (re-maps at each logon)
     - Label as: optional, e.g. Operators Data
     - Drive Letter: select Use → choose M:
     - Leave Connect as / credentials blank
   - On the Common tab:
     - Check "Item-level targeting."
     - Click the "Targeting..."
       - In the Targeting Editor:
       - Click New Item → Security Group
       - In the Group field, click the "..." browse button and select SQUADRON\Operators (or type it)
       - Make sure the condition reads that the user is a member of this group
       - Leave "User in group" (not "Computer in group")
       - Click OK to close the Targeting Editor
       - Click OK to close the mapped drive dialog

*** Create Domain-wide login audit GPO ***

1. New-GPO -Name "Audit - Logon Events" -Comment "Success+Failure logon auditing, domain-wide"
2. New-GPLink -Name "Audit - Logon Events" -Target "DC=squadron,DC=internal"
3. Run 'gpmc.msc' on Win11-Endpoint
4. Expand to squadron.internal → find Audit - Logon Events linked at the domain root.
Right-click → Edit.
   - Navigate: Computer Configuration → Policies → Windows Settings → Security Settings → Advanced Audit Policy Configuration → Audit Policies → Logon/Logoff.
   - In the right pane, double-click "Audit Logon"
   - Check "Configure the following audit events"
   - Tick Success and Failure
   - OK
5. Configure companion policy for a DC, where credential validation actually happens: under Audit Policies → Account Logon, double-click "Audit Credential Validation" → Configure → Success + Failure.

*** Configure Fine-grained Password Policy (Powershell)
1. On Win11-Endpoint: New-ADFineGrainedPasswordPolicy -Name "PSO-Operators" `
    -Precedence 10 `
    -MinPasswordLength 14 `
    -ComplexityEnabled $true `
    -Description "14-char complex password policy for Operators group"
2. Add-ADFineGrainedPasswordPolicySubject -Identity "PSO-Operators" -Subjects "Operators"
3. Verify the PSO exists:
   - Get-ADFineGrainedPasswordPolicy -Identity "PSO-Operators" |
    Select-Object Name, MinPasswordLength, ComplexityEnabled, Precedence
   - Get-ADFineGrainedPasswordPolicySubject -Identity "PSO-Operators"
   - Get-ADUserResultantPasswordPolicy -Identity "sandbox_user" 

*** End-to-end verification of GPOs ***
1. gpupdate /force
2. Get-PSDrive M
3. gpresult /r
4. Get-ADUserResultantPasswordPolicy -Identity "sandbox_user"
5. Get-ADFineGrainedPasswordPolicy -Identity "PSO-Operators"
   - Should see:
     - MinPasswordLength : 14
     - ComplexityEnabled : True
6. auditpol /get /category:"Logon/Logoff"