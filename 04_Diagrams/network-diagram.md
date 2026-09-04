# Squadron Lab — Network Diagram & Reference

**Last updated:** 2026-09-03
**Maintainer:** Justin
**Status:** Correct as of the date above. Update this file in the same commit as any change to addressing, roles, switches, or the internet path.

> A diagram nobody maintains is worse than no diagram, because it is believed.
> When you change the lab, change this file. See the "Change log" and "How to keep this correct" sections at the bottom.

---

## Topology

```
                              INTERNET
                                  |
                                  |  (public / commercial LAN uplink)
                                  |
                    +-------------------------------+
                    |         COMMERCIAL LAN         |
                    |     (home/office network,      |
                    |      DHCP from LAN router)      |
                    +-------------------------------+
                                  |
                                  | <WAN> interface (DHCP-assigned)
                                  |
                  +===============================================+
                  |               INFRA_NODE (Debian)            |
                  |       GATEWAY / DNS / DHCP / NTP / BASTION    |
                  |                                              |
                  |  <WAN> iface  ......  commercial LAN (uplink)|
                  |  Default-Switch iface .. 172.x.x.x (Host mgmt)|
                  |  eth0         ......  10.10.30.1/24 (LAN side)|
                  |                                              |
                  |  Services:                                   |
                  |   - dnsmasq  -> DHCP + authoritative DNS      |
                  |                 domain: squadron.internal     |
                  |                 pool: 10.10.30.100-.200/12h    |
                  |                 reservation: data-node=.116    |
                  |                 SPOOF: update.microsoft.com    |
                  |                        -> 10.10.30.116         |
                  |   - chrony   -> NTP server (stratum src)      |
                  |   - nftables -> NAT (masquerade) + forwarding |
                  |                 + block outbound udp/123       |
                  |   - IP forwarding enabled                     |
                  |   - sshd     -> bastion / ProxyJump target     |
                  +======================eth0====================+
                                  |  10.10.30.1
                                  |
                                  |
                  +-----------------------------------+
                  |   Hyper-V vSwitch: "Lab_Internal" |
                  |   type: Internal                  |
                  |   subnet: 10.10.30.0/24           |
                  +-----------------------------------+
                       |                     |                    (host)
                       |                     |                       |
          +------------+-----+     +---------+--------+     vEthernet (Lab_Internal)
          |  DATA_NODE       |     |  WINDOWS_NODE    |     Hyper-V HOST OS
          |  (Rocky Linux)   |     |  (Windows)       |     10.10.30.2/24 static
          |  10.10.30.116    |     |                  |     gateway: (blank)
          |  (reserved)      |     |  vEthernet(Lab): |     DNS:     (blank)
          |                  |     |  DHCP from       |     -> present on Lab_Internal
          |  Caddy :8080     |     |  Infra 10.10.30.1|        but does NOT route/DNS
          |  DNS: 10.10.30.1 |     |  IPv6: disabled  |        through it (see note)
          |  GW:  10.10.30.1 |     |  on Lab adapter  |
          |  NTP: 10.10.30.1 |     |  DNS: 10.10.30.1 |
          |  SSH: key-only   |     |  GW:  10.10.30.1 |
          +------------------+     +------------------+

  Host access path (bastion):
    Host workstation --ssh--> Infra_Node (172.x.x.x, Default Switch)
                                   |  ProxyJump
                                   v
                              Data_Node (10.10.30.116)   [single command: `ssh data-node`]
```

---

## Addressing table

| Host          | OS          | Interface (Lab)      | Lab IP           | Assigned by         | Gateway     | DNS         | NTP source   |
|---------------|-------------|----------------------|------------------|---------------------|-------------|-------------|--------------|
| Infra_Node    | Debian      | eth0                 | 10.10.30.1/24    | static              | (uplink)    | self/upstream | public pool |
| Infra_Node    | Debian      | \<WAN\>              | DHCP             | commercial LAN      | LAN router  | LAN/upstream | public pool |
| Infra_Node    | Debian      | Default Switch       | 172.x.x.x (DHCP) | Hyper-V Default Sw. | Hyper-V NAT | —           | —           |
| Data_Node     | Rocky Linux | eth0 / ensX          | 10.10.30.116     | Infra (reservation) | 10.10.30.1  | 10.10.30.1  | 10.10.30.1   |
| Windows_Node  | Windows     | vEthernet (Lab)      | 10.10.30.100-200 | Infra (dnsmasq)     | 10.10.30.1  | 10.10.30.1  | 10.10.30.1   |
| Hyper-V Host  | Windows     | vEthernet (Lab_Int.) | 10.10.30.2/24    | static              | (blank)     | (blank)     | n/a          |
| Hyper-V Host  | Windows     | Ethernet ("commercial") | DHCP          | commercial LAN      | LAN router  | LAN         | n/a          |

DHCP pool: **10.10.30.100 – 10.10.30.200**, 12h lease. Static/reserved addresses (.1 Infra, .2 Host) sit outside the pool. **Data_Node is pinned to .116 via a `dhcp-host=` reservation** (inside the pool range but reserved to its MAC).

> **Note — Infra_Node Default Switch IP (172.x.x.x) is not stable.** Hyper-V's Default Switch is NAT'd and can change its subnet across host reboots. The Host's `~/.ssh/config` `infra` block and the ProxyJump path depend on this address; if the jump breaks after a host reboot, re-check the Infra_Node's Default Switch address first.

---

## Roles & services

**Infra_Node (Debian) — the lynchpin and bastion.** Only path between the lab and the internet, and the only host the Host workstation can reach directly.
- **dnsmasq** (compiled from source, `/usr/local/sbin/dnsmasq`): DHCP + authoritative DNS for `squadron.internal`. Bound to eth0 (10.10.30.1) with `bind-interfaces`. Serves DHCP option:router, option:dns-server, and option:ntp-server all = 10.10.30.1.
  - **Reservation:** `dhcp-host=<data-node-MAC>,data-node,10.10.30.116` pins the Data_Node.
  - **DNS spoof (intentional, lab exercise):** `address=/update.microsoft.com/10.10.30.116` — any internal query for `update.microsoft.com` resolves to the Data_Node. This is a deliberate teaching artifact, not a compromise.
- **chrony**: syncs to public NTP pool upstream; serves time to 10.10.30.0/24 (`allow`). `local stratum 10` for isolated operation.
- **nftables**: `ip nat` masquerade for 10.10.30.0/24 out \<WAN\>; `ip filter forward` allows lab<->WAN; **drops forwarded udp/123** so lab clients cannot reach public NTP (no fallback — Infra is the only time source).
- **IP forwarding**: `net.ipv4.ip_forward=1` (persistent).
- **sshd**: bastion. The Host authenticates here by key, then ProxyJumps to the Data_Node.

**Data_Node (Rocky Linux).**
- Reserved DHCP address 10.10.30.116. DNS + NTP + gateway all point at 10.10.30.1.
- Extra 4GB disk: `sdb1` ext4 -> `/mnt/ops_data`, `sdb2` xfs -> `/mnt/log_data` (mounted **by UUID** in fstab).
- `cyber_team` group; users `alpha`, `bravo`; shared dir `/mnt/ops_data/shared` (SGID+sticky, `3770`).
- **Caddy web server**: serves a static page from `/var/www/html` on **port 8080 only** (`:8080` bind, all interfaces, plain HTTP). Reachable off-box from Infra_Node.
- **SSH: key-only, passwords disabled.** Authorized keys: **three identities** — Infra_Node, Windows_Node, Host workstation (see SSH trust below).
- **metrics-logger.service**: writes CPU/RAM to `/mnt/log_data/metrics.log` every 30s; systemd-supervised, restarts on death, starts on boot.

**Windows_Node (Windows).**
- DHCP client of Infra.
- OpenSSH client present (checked via `Get-WindowsCapability -Online | ? Name -like 'OpenSSH.Client*'`).
- Own ed25519 key pair; public key authorized on Data_Node.
- Scheduled Task **LabOps-PullMetrics** (every 5 min): SSH to Data_Node, copy `metrics.log` to `C:\ProgramData\LabOps\`. Runs as key-owning user.
- **IPv6 disabled on the Lab_Internal adapter** — required for the DNS-spoof exercise; the spoof poisons only IPv4 A-records, and Windows' dual-stack preference could otherwise resolve/route around it.

**Hyper-V Host.**
- Sits on Lab_Internal via `vEthernet (Lab_Internal)`, statically set to 10.10.30.2 with **blank gateway and DNS** so it does not take a lease or route lab-ward. Its internet/management path is the separate "commercial" NIC.

**Host workstation (physical).**
- Reaches the lab only through the Infra_Node bastion. `~/.ssh/config` defines `infra` (bastion) and `data-node` (`ProxyJump infra`), so `ssh data-node` opens a shell on the Data_Node in one command with no interactive hop.
- Passphrase-protected ed25519 key; OpenSSH Authentication Agent service enabled (Automatic) so the passphrase is entered once.
- Access method is **ProxyJump, not agent forwarding** — the bastion is a transport only and never gains use of the Host's keys.

---

## Internet path

```
Data_Node / Windows_Node
        |  default route -> 10.10.30.1
        v
Infra_Node eth0 (10.10.30.1)
        |  IP forwarding + nftables NAT (masquerade)
        v
Infra_Node <WAN>  ->  commercial LAN  ->  internet
```

Lab nodes have **no direct internet path** — every packet is NATed through Infra_Node. NTP (udp/123) is deliberately blocked on this path so lab clients cannot bypass Infra_Node for time.

---

## Host access path (bastion / jump host)

```
Host workstation
      |  ssh data-node   (single command)
      |  key auth to Infra_Node on 172.x.x.x (Default Switch)
      v
Infra_Node (bastion, ProxyJump)   <-- transport only, no shell, no agent access
      |  tunneled connection to 10.10.30.116:22
      v
Data_Node  (Host key authenticates end-to-end)
```

- Defined once in the Host's `~/.ssh/config` (`Host infra` + `Host data-node` with `ProxyJump infra`).
- **Local port forward for the web page:** `ssh -L 9090:localhost:8080 data-node` → browse `http://localhost:9090` on the Host to view the Data_Node's Caddy page through the tunnel.
- ProxyJump chosen over agent forwarding deliberately (see README security notes).

---

## SSH trust (who can reach Data_Node)

Data_Node is key-only. `~/.ssh/authorized_keys` holds **three** keys:

| Key comment                     | Belongs to        | Private key location                          |
|---------------------------------|-------------------|-----------------------------------------------|
| `infra-node -> data-node`       | Infra_Node        | Infra_Node `~/.ssh/id_ed25519`                |
| `windows-node -> data-node`     | Windows_Node      | Windows_Node `%USERPROFILE%\.ssh\id_ed25519`  |
| `host-workstation -> data-node` | Host workstation  | Host `%USERPROFILE%\.ssh\id_ed25519` (passphrase-protected) |

The Host workstation's key is also authorized on the **Infra_Node** (`host-workstation -> infra-node`) for the bastion hop.

Distinguish which machine connected via the Data_Node's own logs:
```bash
sudo journalctl -u sshd | grep "Accepted publickey"      # shows SHA256 fingerprint + source IP
ssh-keygen -lf ~/.ssh/authorized_keys                    # maps fingerprint -> key comment
```

> **Host key note:** the Data_Node's SSH *host* keys were regenerated during the bastion exercise. Any client that pinned the old host key refuses to reconnect (`REMOTE HOST IDENTIFICATION HAS CHANGED`) until the stale `known_hosts` entry is cleared with `ssh-keygen -R`. `accept-new` does not rescue a *changed* key, only a missing one. An unexpected host-key change in the wild is a sign of possible interception.

---

## DNS domain & records

- Internal domain: **`squadron.internal`** (IANA-reserved special-use TLD; chosen over `.local` to avoid mDNS/Bonjour conflicts).
- dnsmasq is authoritative for it (`local=/squadron.internal/`, `domain=squadron.internal`, `expand-hosts`). Queries for this domain are never forwarded upstream.
- **Spoofed record (intentional lab artifact):** `update.microsoft.com -> 10.10.30.116` via `address=/update.microsoft.com/10.10.30.116`. Documented so it is not mistaken for a real compromise.

---

## How to keep this correct

Update this file **in the same commit** as the change whenever any of these move:
- an IP, subnet, DHCP pool, lease time, or reservation
- a host's role, OS, or a service it runs (dnsmasq / chrony / nftables / sshd / Caddy / scheduled tasks)
- the Lab_Internal switch (type, name, subnet)
- the internet/uplink path or NAT config
- an SSH trust relationship (a new authorized key = a new row in the SSH trust table)
- the Host access / bastion path (config aliases, jump address, tunnels)
- any DNS record, including the intentional spoof
- storage layout, users/groups, or anything else represented above

Quick self-check commands to confirm reality matches this doc:
```bash
# Infra_Node
ip -br addr ; ip route show default
sudo nft list ruleset
chronyc sources -v
grep -E 'interface|dhcp-range|dhcp-option|dhcp-host|domain|local|address=' /etc/dnsmasq.conf
cat /var/lib/misc/dnsmasq.leases

# Data_Node
ip -br addr ; ip route show default
cat /etc/resolv.conf ; chronyc -n sources
ss -tlnp | grep :8080                                    # Caddy listening
cat ~/.ssh/authorized_keys ; ssh-keygen -lf ~/.ssh/authorized_keys

# Host workstation
ssh -G data-node | Select-String "hostname|proxyjump|user"   # PowerShell: confirms jump config
```

---

## Change log

| Date       | Change                                                                 | By     |
|------------|------------------------------------------------------------------------|--------|
| 2026-09-01 | Initial diagram: DHCP/DNS/NTP/NAT on Infra, key-only SSH, storage +     | Justin |
|            | users on Data_Node, metrics pull on Windows_Node.                      |        |
| 2026-09-03 | Data_Node pinned to 10.10.30.116 (reservation). Added Caddy :8080 web  | Justin |
|            | server; intentional DNS spoof (update.microsoft.com -> .116); IPv6     |        |
|            | disabled on Windows_Node Lab adapter for the spoof. Formalized bastion |        |
|            | access: Host key path, ProxyJump config, local port forward 9090->8080.|        |
|            | Data_Node SSH trust now three identities (added Host workstation).     |        |
|            | Data_Node host keys regenerated (known_hosts re-pin required).         |        |
