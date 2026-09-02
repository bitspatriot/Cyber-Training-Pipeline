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