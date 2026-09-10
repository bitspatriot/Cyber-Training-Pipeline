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

*** Preperation steps before running the pgSense installer ***
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
1. Set-DnsServerForwarder -IPAddress 8.8.8.8, 1.1.1.1
2. Test that the DC now resolved both internal and external DNS names:
   - Internal: Resolve-DnsName squadron.internal
   - External: Resolve-DnsName google.com
  