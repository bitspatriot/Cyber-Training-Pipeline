# Squadron Lab

A self-contained, three-node virtual lab running on Hyper-V, built to stand on its own: its own DHCP, authoritative DNS, NAT gateway, internal time source, key-only SSH, and cross-node monitoring. The lab starts from a network where nothing hands out addresses and ends as a hardened internal segment that reaches the internet through a single controlled gateway.

**Status:** Active · **Last updated:** 2026-09-01 · **Maintainer:** Justin

---

## Table of contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Hosts](#hosts)
- [Prerequisites](#prerequisites)
- [Setup order](#setup-order)
- [Node configuration](#node-configuration)
- [Verification](#verification)
- [Operations](#operations)
- [Troubleshooting](#troubleshooting)
- [Conventions](#conventions)
- [Related documents](#related-documents)

---

## Overview

The lab models a small isolated network where the infrastructure host provides every core service the other machines depend on. There is no external DHCP or DNS on the internal segment — the Infra_Node *is* the network's DHCP server, DNS resolver, default gateway, NAT router, and NTP source. The two other nodes boot with no addressing and receive everything from the Infra_Node.

Design goals:

- **Single controlled path to the internet.** All internal traffic is NATed through the Infra_Node; nothing on the lab segment routes out on its own.
- **Authoritative internal naming.** One consistent domain (`squadron.internal`) served authoritatively, never leaked upstream.
- **One time source, enforced.** Clients take time only from the Infra_Node; outbound public NTP is blocked at the gateway so there is no silent fallback.
- **Key-only access.** Password SSH is disabled on the Data_Node; access is by authorized key only, and every trusting relationship is documented and auditable.
- **Maintained documentation.** The network diagram and this README are kept correct as the lab changes.

---

## Architecture

```
INTERNET
   |
COMMERCIAL LAN (upstream DHCP)
   |
   | <WAN>
INFRA_NODE (Debian) ── gateway / DNS / DHCP / NTP / NAT
   | eth0  10.10.30.1/24
   |
Hyper-V vSwitch "Lab_Internal" (Internal, 10.10.30.0/24)
   |                         |
DATA_NODE (Rocky)      WINDOWS_NODE (Windows)
10.10.30.100-200       10.10.30.100-200
```

Full detail — addressing table, per-service breakdown, internet path, and SSH trust — lives in [`network-diagram.md`](./network-diagram.md).

---

## Hosts

| Host           | OS          | Lab IP            | Role                                                        |
|----------------|-------------|-------------------|------------------------------------------------------------|
| Infra_Node     | Debian      | 10.10.30.1 (static) | Gateway, DHCP, authoritative DNS, NTP server, NAT router  |
| Data_Node      | Rocky Linux | 10.10.30.100-200 (DHCP) | Storage host, key-only SSH target, metrics producer   |
| Windows_Node   | Windows     | 10.10.30.100-200 (DHCP) | Metrics collector (scheduled pull over SSH)           |
| Hyper-V Host   | Windows     | 10.10.30.2 (static) | Virtualization host; on Lab_Internal but does not route   |

Internal domain: **`squadron.internal`**. DHCP pool: **10.10.30.100–.200**, 12h lease.

---

## Prerequisites

- A Hyper-V host with an **Internal** virtual switch named `Lab_Internal` (subnet 10.10.30.0/24) and an uplink path to the internet (the "commercial" NIC).
- Three VMs: Debian (Infra), Rocky Linux (Data), Windows (Windows_Node). Generation 2 VMs boot UEFI — ensure the install ISO is UEFI-bootable and boot order lists the DVD first.
- Console access to each VM (the initial build happens before any network path exists).

---

## Setup order

The order matters — several steps depend on the one before, and doing them out of order turns a task into a recovery exercise.

1. **Infra_Node addressing** — give eth0 a static `10.10.30.1/24` on Lab_Internal.
2. **DHCP + DNS** — build and configure dnsmasq to serve the pool and resolve `squadron.internal`.
3. **NAT + forwarding** — enable IP forwarding and nftables masquerade so the lab can reach the internet.
4. **NTP** — chrony syncs upstream and serves the lab; block outbound udp/123 for lab clients.
5. **Key-only SSH** — authorize keys on the Data_Node, verify key auth works, *then* disable passwords.
6. **Storage, users, monitoring** — Data_Node disks/users; metrics daemon; Windows scheduled pull.
7. **Documentation** — network diagram + this README, kept current.

---

## Node configuration

### Infra_Node (Debian)

- **Static IP:** eth0 = `10.10.30.1/24` (systemd-networkd `.network` unit; `[Match] Name=eth0`).
- **dnsmasq** (compiled from source → `/usr/local/sbin/dnsmasq`, run via a custom systemd unit):
  - `interface=eth0`, `bind-interfaces`, `listen-address=10.10.30.1`
  - `dhcp-range=10.10.30.100,10.10.30.200,255.255.255.0,12h`
  - `dhcp-option=option:router,10.10.30.1`, `option:dns-server,10.10.30.1`, `option:ntp-server,10.10.30.1`
  - `domain=squadron.internal`, `local=/squadron.internal/`, `expand-hosts`
- **Routing/NAT** (nftables):
  - `net.ipv4.ip_forward=1` (persistent in `/etc/sysctl.d/`)
  - `ip nat postrouting`: masquerade `10.10.30.0/24` out `<WAN>`
  - `ip filter forward`: allow lab↔WAN (established/related back), **drop forwarded udp/123**
  - Ruleset saved to `/etc/nftables.conf`; `nftables.service` enabled.
- **chrony:** `pool ... iburst` upstream; `allow 10.10.30.0/24`; `local stratum 10`.

### Data_Node (Rocky Linux)

- **DHCP client** of Infra (NetworkManager). DNS/NTP/gateway all resolve to 10.10.30.1.
- **Storage:** 4GB disk → `sdb1` ext4 `/mnt/ops_data`, `sdb2` xfs `/mnt/log_data`. Mounted **by UUID** in `/etc/fstab`.
- **Users:** group `cyber_team`; users `alpha`, `bravo`. Shared dir `/mnt/ops_data/shared` set `3770` (SGID + sticky) and group `cyber_team`.
- **SSH:** `PasswordAuthentication no`, key-only. Two authorized keys (Infra_Node, Windows_Node).
- **chrony client:** `server 10.10.30.1 iburst` only; public pools removed.
- **metrics-logger.service:** runs `/usr/local/bin/metrics-logger.sh`, appending timestamped CPU/RAM to `/mnt/log_data/metrics.log` every 30s. `Restart=always`, enabled at boot, `RequiresMountsFor=/mnt/log_data`.

### Windows_Node (Windows)

- **DHCP client** of Infra.
- **OpenSSH client** present (capability check recorded — see Conventions).
- **SSH identity:** own ed25519 key pair; public key authorized on the Data_Node. Private key stays on the Windows_Node.
- **Scheduled task `LabOps-PullMetrics`:** every 5 minutes, SSH to the Data_Node, read `/mnt/log_data/metrics.log`, write to `C:\ProgramData\LabOps\`. Runs as the key-owning user so the key resolves under that profile.

### Hyper-V Host

- `vEthernet (Lab_Internal)` set static to **10.10.30.2/24 with blank gateway and DNS** — present on the segment for management but never taking a lease or routing/resolving through Infra. Internet/management goes over the separate "commercial" NIC.

---

## Verification

Quick checks that the lab is behaving. Run per node.

**Infra_Node**
```bash
ip -br addr; ip route show default          # eth0 = 10.10.30.1; default via <WAN>
sudo ss -ulpn | grep -E ':67|:53'           # dnsmasq bound to 10.10.30.1 only
sudo nft list ruleset                        # masquerade + forward + udp/123 drop present
chronyc sources -v                           # upstream pool selected (^*)
cat /var/lib/misc/dnsmasq.leases             # leases handed to Data/Windows nodes
```

**Data_Node**
```bash
ip route show default                        # default via 10.10.30.1
cat /etc/resolv.conf                         # nameserver 10.10.30.1, search squadron.internal
ping -c3 8.8.8.8; ping -c3 google.com        # NAT + DNS working
chronyc -n sources                           # source = 10.10.30.1
systemctl status metrics-logger.service      # active
tail -f /mnt/log_data/metrics.log            # new line every 30s
```

**Windows_Node**
```powershell
ssh -i $env:USERPROFILE\.ssh\id_ed25519 <user>@10.10.30.x "tail -5 /mnt/log_data/metrics.log"
Start-ScheduledTask -TaskName "LabOps-PullMetrics"
Get-Content C:\ProgramData\LabOps\metrics.log -Tail 5
```

**Proof points captured during the build**
- DHCP: Data/Windows nodes lease from 10.10.30.100–.200.
- NTP no-fallback: skew a client clock, `chronyc makestep`, confirm correction with `chronyc tracking` (Reference ID = 10.10.30.1); outbound udp/123 to a public host times out.
- SSH audit: `journalctl -u sshd | grep "Accepted publickey"` + `ssh-keygen -lf ~/.ssh/authorized_keys` map each connection to a machine.
- Monitoring survives reboot: `metrics.log` gains newer timestamps after a Data_Node reboot; service is `enabled`.

---

## Operations

**Release/renew a lease (Data_Node, NetworkManager):**
```bash
sudo nmcli device reapply <iface>            # or: disconnect && connect
```

**Restart core services (Infra_Node):**
```bash
sudo systemctl restart dnsmasq
sudo systemctl restart chrony
sudo systemctl restart nftables
```

**Watch DHCP/DNS activity live (Infra_Node):**
```bash
journalctl -u dnsmasq -f
```

**Add an SSH identity to the Data_Node:** append the new public key to `~/.ssh/authorized_keys`, give it a descriptive `-C` comment naming its machine, and add a row to the SSH trust table in `network-diagram.md`.

---

## Troubleshooting

| Symptom | Likely cause | Where to look |
|---|---|---|
| A machine that shouldn't be on the lab pulls a 10.10.30.x lease and loses internet/DNS | It has an adapter on Lab_Internal and took a lease; DNS/gateway repointed to 10.10.30.1 | `cat /var/lib/misc/dnsmasq.leases`; set that adapter static with blank gateway/DNS, or move switch to Private |
| Lab nodes get an IP but can't reach the internet | IP forwarding off, or NAT on the wrong interface | `sysctl net.ipv4.ip_forward`; `nft list ruleset` — masquerade must be on `<WAN>` |
| `ping 8.8.8.8` works but `google.com` doesn't | DNS, not routing | `/etc/resolv.conf` should point at 10.10.30.1; check dnsmasq |
| Client won't take time from Infra / shows "Not synchronised" after skew | chrony won't step a large offset unattended | `chronyc makestep`; confirm source reachable with `chronyc -n sources` |
| `apt`/download fails on Infra during build | No outbound path yet, or empty sources | Infra needs its `<WAN>` NIC up; check `/etc/apt/sources.list` |
| Windows scheduled task runs but log stays empty | Script error (e.g. reserved `$host` var), or key not found under the task's account | Add error logging to the pull script; confirm task runs as the key-owning user |
| `ssh`/`scp` refused on a host | `sshd` not installed/running on that host | `systemctl status ssh` (Debian) / `Get-Service sshd` (Windows) |
| PowerShell mangles a Windows path with `\\` | Inline `$env:` expansion quoting | Use `Join-Path`, or `cd` and pass a relative path |

---

## Conventions

- **Internal domain:** `squadron.internal` (IANA-reserved `.internal`, chosen over `.local` to avoid mDNS conflicts).
- **Addressing:** Infra `.1`, Hyper-V host `.2`, DHCP pool `.100–.200`. Statics live outside the pool.
- **Mounts:** always by **UUID** in fstab, never `/dev/sdX` (device names can reorder across boots).
- **SSH keys:** ed25519; every key carries a `-C` comment naming its source machine (e.g. `windows-node -> data-node`). Private keys never leave their machine — only public keys are copied.
- **OpenSSH client check (Windows), recorded:**
  ```powershell
  Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Client*'
  ```
- **Firewall block before proof:** enforce the NTP outbound block before demonstrating the client syncs, so the demonstration is proof and not coincidence.
- **Documentation discipline:** update `network-diagram.md` and this README in the same commit as any change to addressing, roles, services, switches, the internet path, or SSH trust.

---

## Related documents

- [`network-diagram.md`](./network-diagram.md) — topology, full addressing table, per-service detail, internet path, SSH trust, and change log.
