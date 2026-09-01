# Squadron Lab — Network Diagram & Reference

**Last updated:** 2026-09-01
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
                  |            GATEWAY / DNS / DHCP / NTP         |
                  |                                              |
                  |  <WAN> iface  ......  commercial LAN (uplink)|
                  |  eth0         ......  10.10.30.1/24 (LAN side)|
                  |                                              |
                  |  Services:                                   |
                  |   - dnsmasq  -> DHCP + authoritative DNS      |
                  |                 domain: squadron.internal     |
                  |                 pool: 10.10.30.100-.200/12h    |
                  |   - chrony   -> NTP server (stratum src)      |
                  |   - nftables -> NAT (masquerade) + forwarding |
                  |                 + block outbound udp/123       |
                  |   - IP forwarding enabled                     |
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
          |                  |     |                  |     gateway: (blank)
          |  eth0/ensX:      |     |  vEthernet(Lab): |     DNS:     (blank)
          |  DHCP from       |     |  DHCP from       |     -> present on Lab_Internal
          |  Infra 10.10.30.1|     |  Infra 10.10.30.1|        but does NOT route/DNS
          |                  |     |                  |        through it (see note)
          |  DNS: 10.10.30.1 |     |  DNS: 10.10.30.1 |
          |  GW:  10.10.30.1 |     |  GW:  10.10.30.1 |
          |  NTP: 10.10.30.1 |     |                  |
          +------------------+     +------------------+
```

---

## Addressing table

| Host          | OS          | Interface (Lab)      | Lab IP           | Assigned by      | Gateway     | DNS         | NTP source   |
|---------------|-------------|----------------------|------------------|------------------|-------------|-------------|--------------|
| Infra_Node    | Debian      | eth0                 | 10.10.30.1/24    | static           | (uplink)    | self/upstream | public pool |
| Infra_Node    | Debian      | \<WAN\>              | DHCP             | commercial LAN   | LAN router  | LAN/upstream | public pool |
| Data_Node     | Rocky Linux | eth0 / ensX          | 10.10.30.100-200 | Infra (dnsmasq)  | 10.10.30.1  | 10.10.30.1  | 10.10.30.1   |
| Windows_Node  | Windows     | vEthernet (Lab)      | 10.10.30.100-200 | Infra (dnsmasq)  | 10.10.30.1  | 10.10.30.1  | 10.10.30.1   |
| Hyper-V Host  | Windows     | vEthernet (Lab_Int.) | 10.10.30.2/24    | static           | (blank)     | (blank)     | n/a          |
| Hyper-V Host  | Windows     | Ethernet ("commercial") | DHCP          | commercial LAN   | LAN router  | LAN         | n/a          |

DHCP pool: **10.10.30.100 – 10.10.30.200**, 12h lease. Static/reserved addresses (.1, .2) sit outside the pool.

---

## Roles & services

**Infra_Node (Debian) — the lynchpin.** Only path between the lab and the internet.
- **dnsmasq** (compiled from source, `/usr/local/sbin/dnsmasq`): DHCP + authoritative DNS for `squadron.internal`. Bound to eth0 (10.10.30.1) with `bind-interfaces`. Serves DHCP option:router, option:dns-server, and option:ntp-server all = 10.10.30.1.
- **chrony**: syncs to public NTP pool upstream; serves time to 10.10.30.0/24 (`allow`). `local stratum 10` for isolated operation.
- **nftables**: `ip nat` masquerade for 10.10.30.0/24 out \<WAN\>; `ip filter forward` allows lab<->WAN; **drops forwarded udp/123** so lab clients cannot reach public NTP (no fallback — Infra is the only time source).
- **IP forwarding**: `net.ipv4.ip_forward=1` (persistent).

**Data_Node (Rocky Linux).**
- DHCP client of Infra. DNS + NTP + gateway all point at 10.10.30.1.
- Extra 4GB disk: `sdb1` ext4 -> `/mnt/ops_data`, `sdb2` xfs -> `/mnt/log_data` (mounted by UUID in fstab).
- `cyber_team` group; users `alpha`, `bravo`; shared dir `/mnt/ops_data/shared` (SGID+sticky, `3770`).
- **SSH: key-only, passwords disabled.** Authorized keys: **two identities** — Infra_Node and Windows_Node (see SSH trust below).
- **metrics-logger.service**: writes CPU/RAM to `/mnt/log_data/metrics.log` every 30s; systemd-supervised, restarts on death, starts on boot.

**Windows_Node (Windows).**
- DHCP client of Infra.
- OpenSSH client present (checked via `Get-WindowsCapability -Online | ? Name -like 'OpenSSH.Client*'`).
- Own ed25519 key pair; public key authorized on Data_Node.
- Scheduled Task **LabOps-PullMetrics** (every 5 min): SSH to Data_Node, copy `metrics.log` to `C:\ProgramData\LabOps\`. Runs as key-owning user.

**Hyper-V Host.**
- Sits on Lab_Internal via `vEthernet (Lab_Internal)`, statically set to 10.10.30.2 with **blank gateway and DNS** so it does not take a lease or route lab-ward. Its internet/management path is the separate "commercial" NIC.

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

## SSH trust (who can reach Data_Node)

Data_Node is key-only. `~/.ssh/authorized_keys` holds **two** keys:

| Key comment                  | Belongs to    | Private key location                  |
|------------------------------|---------------|---------------------------------------|
| `infra-node -> data-node`    | Infra_Node    | Infra_Node `~/.ssh/id_ed25519`        |
| `windows-node -> data-node`  | Windows_Node  | Windows_Node `%USERPROFILE%\.ssh\id_ed25519` |

Distinguish which machine connected via the Data_Node's own logs:
```bash
sudo journalctl -u sshd | grep "Accepted publickey"      # shows SHA256 fingerprint + source IP
ssh-keygen -lf ~/.ssh/authorized_keys                    # maps fingerprint -> key comment
```

---

## DNS domain

- Internal domain: **`squadron.internal`** (IANA-reserved special-use TLD; chosen over `.local` to avoid mDNS/Bonjour conflicts).
- dnsmasq is authoritative for it (`local=/squadron.internal/`, `domain=squadron.internal`, `expand-hosts`). Queries for this domain are never forwarded upstream.

---

## How to keep this correct

Update this file **in the same commit** as the change whenever any of these move:
- an IP, subnet, DHCP pool, or lease time
- a host's role, OS, or a service it runs (dnsmasq / chrony / nftables / sshd / scheduled tasks)
- the Lab_Internal switch (type, name, subnet)
- the internet/uplink path or NAT config
- an SSH trust relationship (a new authorized key = a new row in the SSH trust table)
- storage layout, users/groups, or anything else represented above

Quick self-check commands to confirm reality matches this doc:
```bash
# Infra_Node
ip -br addr ; ip route show default
sudo nft list ruleset
chronyc sources -v
cat /etc/dnsmasq.conf | grep -E 'interface|dhcp-range|dhcp-option|domain|local'
cat /var/lib/misc/dnsmasq.leases

# Data_Node
ip -br addr ; ip route show default
cat /etc/resolv.conf ; chronyc -n sources
cat ~/.ssh/authorized_keys ; ssh-keygen -lf ~/.ssh/authorized_keys
```

---

## Change log

| Date       | Change                                                        | By     |
|------------|---------------------------------------------------------------|--------|
| 2026-09-01 | Initial diagram: DHCP/DNS/NTP/NAT on Infra, key-only SSH,      | Justin |
|            | storage + users on Data_Node, metrics pull on Windows_Node.   |        |
