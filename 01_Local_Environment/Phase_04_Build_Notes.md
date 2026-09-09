# Task 4.1: Plumbing and Segmentation

*** Unpack the pfSense Image ***
1. From Powershell on the Host running Hyper-V: Invoke-WebRequest -Uri "https://atxfiles.netgate.com/mirror/downloads/pfSense-CE-2.7.2-RELEASE-amd64.iso.gz" -OutFile pfSense.iso.gz
2. Install 7-Zip on Host: winget install --id 7zip.7zip -e --source winget
3. Unpack the pfSense .gz ISO: & "C:\Program Files\7-Zip\7z.exe" e pfSense.iso.gz
4. Verify you have the real pfSense ISO and not a truncated download: Get-Item $env:USERPROFILE\Downloads\pfSense.iso | Select-Object Name, Length
   - ISO filesize should be several hundred MBs

*** Create the pfSense VM (two adapters) ***
IMPORTANT NOTE: Make the pfSense a Generation 1 VM

In Powershell:
$vmName   = "pfSense"
$vhdPath  = "C:\Hyper-V\pfSense\pfSense.vhdx"
$isoPath  = "$env:USERPROFILE\Downloads\pfSense.iso"

New-VM -Name $vmName -Generation 1 -MemoryStartupBytes 2GB -NewVHDPath $vhdPath -NewVHDSizeBytes 20GB
Set-VMMemory $vmName -DynamicMemoryEnabled $false

*** Attach the install ISO ***
Set-VMDvdDrive -VMName $vmName -Path $isoPath

*** Create two network adapters ***
1. Adapter 1 (WAN, connected to the Default Switch (path to internet)): Connect-VMNetworkAdapter -VMName $vmName -Name "Network Adapter" -SwitchName "Default Switch"
2. Adapter 2 (LAN trunk on Lab_Internal switch (carries all three VLANS)): Add-VMNetworkAdapter -VMName $vmName -Name "LAN-Trunk" -SwitchName "Lab_Internal"