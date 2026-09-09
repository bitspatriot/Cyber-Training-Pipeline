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