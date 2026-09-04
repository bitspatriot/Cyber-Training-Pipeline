$dest = "C:\ProgramData\LabOps\metrics.log"
$key = "$env:USERPROFILE\.ssh\id_ed25519"
$user = "sandbox_user"
$host = "10.10.30.116"

ssh -i $key -o StrictHostKeyChecking=accept-new "$user@$host" "cat /mnt/log_data/metrics.log" | Out-File -FilePath $dest -Encoding utf8