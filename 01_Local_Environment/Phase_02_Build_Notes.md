# Task 2.1: Caddy Web Server

*** Install the caddy repository and web server ***
1. sudo dnf install -y 'dnf-command(copr)'
2. sudo dnf copr enable -y @caddy/caddy
3. sudo dnf install -y caddy
4. Verify Install: caddy version

*** Create the HTML page ***
1. sudo mkdir -p /var/www/html
2. Create index.html file in /var/www/html (Caddy 'index.html' page pushed to '02_Config_Files -> 'caddy_web_Server')
3. Configure the Caddfile that listens on port :8080 from all hosts, and not just 'localhost.'
   - New Caddy file created to replace existing /etc/caddy/Caddyfile ('Caddyfile' pushed to '02_Config_Files -> 'caddy_web_Server')
4. Validate the Caddyfile config: caddy validate --config /etc/caddy/Caddyfile
5. SELINUX (Rocky) tripwires: SELINUX can block serving websites from certain directories, or from binding to a non-standarp port (e.g. 8080) Fixes:
   - ls -Zd /var/www/html
   - sudo restorecon -Rv /var/www/html
   - sudo semanage port -l | grep http_port_t
   - If 8080 isn't listed in http_port_t: sudo semanage port -a -t http_port_t -p tcp 8080

*** Start Caddy ***
1. sudo systemctl enable --now caddy
2. sudo systemctl status caddy --no-pager
3. Confirm the web server is listening on port 8080: sudo ss -tlnp | grep :8080
- Should see: 0.0.0.0:8080 (or *:8080) — not 127.0.0.1:8080

*** Open the firewall to enable "answers off-box" capability ***
1. Confirm host firewall that's active: sudo systemctl is-active firewalld nftables (Should be firewalld for Rocky Linux)
2. sudo firewall-cmd --permanent --add-port=8080/tcp
3. sudo firewall-cmd --reload
4. sudo firewall-cmd --list-ports    
5. Verify: confirm '8080/tcp' present

*** Prove the web server answeres requests from the Infra_Node ***
1. Install 'curl': sudo apt install curl
2. From the Infra_Node: curl -v http://10.10.30.x:8080/
3. Should she '200 OK' and the contents of index.html

# Task 2.2: Network-Wide DNS Spoofing
1. sudo nano /etc/dnsmasq.conf
2. Bind Data_Node IP lease so it doesn't receive a new address and break the spoofing at the end it's 12H lease: dhcp-host=<data-node-MAC>,data-node,10.10.30.116 (or whatever Data_Node's IP is)
   - Grab MAC from dnsmasq if unknown: grep 10.10.30.116 /var/lib/misc/dnsmasq.leases
   - If you bound Data_Node to a new IP, force it to pick up the new reservation: sudo nmcli device reapply <iface>
3. sudo /usr/local/sbin/dnsmasq --test
4. sudo systemctl restart dnsmasq
5. Install 'dig': sudo apt install dnsutils
6. Verify the spoo resolves from the Infra_Node: dig @10.10.30.1 update.microsoft.com +short
   - Should return <Data_Node IP> and not the real microsoft address

*** Disable IPv6 on the Windows_Node's Lab_Internal adapter from Powershell ***
1. 
