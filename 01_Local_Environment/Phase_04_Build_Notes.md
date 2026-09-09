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