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