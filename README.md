# Squadron Lab

A self-contained, three-node virtual lab running on Hyper-V, built to stand on its own: its own DHCP, authoritative DNS, NAT gateway, internal time source, key-only SSH, a bastion access model, cross-node monitoring, and a web service. The lab starts from a network where nothing hands out addresses and ends as a hardened internal segment reachable only through a single controlled gateway.

**Status:** Active · **Last updated:** 2026-09-03 · **Maintainer:** Justin

---

## Table of contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Hosts](#hosts)
- [Prerequisites](#prerequisites)
- [Setup order](#setup-order)
- [Node configuration](#node-configuration)
- [Access model (bastion)](#access-model-bastion)
- [Services](#services)
- [Verification](#verification)
- [Operations](#operations)
- [Troubleshooting](#troubleshooting)
- [Known issues](#known-issues)
- [Conventions](#conventions)
- [Security notes](#security-notes)
- [Related documents](#related-documents)

---

## Overview

The lab models a small isolated network where the infrastructure host provides every core service the other machines depend on. There is no external DHCP or DNS on the internal segment — the Infra_Node *is* the network's DHCP server, DNS resolver, default gateway, NAT router, NTP source, and SSH bastion. The other nodes boot with no addressing and receive everything from the Infra_Node, and the physical Host workstation can reach the lab only by jumping through it.

Design goals:

- **Single controlled path to the internet.** All internal traffic is NATed through the Infra_Node; nothing on the lab segment routes out on its own.
- **Authoritative internal naming.** One consistent domain (`squadron.internal`) served authoritatively, never leaked upstream.
- **One time source, enforced.** Clients take time only from the Infra_Node; outbound public NTP is blocked at the gateway so there is no silent fallback.
- **Key-only access through a bastion.** Password SSH is disabled on the Data_Node; the only route in from the Host is a single-command ProxyJump through the Infra_Node. Every trust relationship is documented and auditable.
- **Maintained documentation.** The network diagram and this README are kept correct as the lab changes, and history is scanned for secrets before a phase closes.

---

## Architecture

```
INTERNET
   |
COMMERCIAL LAN (upstream DHCP)
   |
   | <WAN>
INFRA_NODE (Debian) ── gateway / DNS / DHCP / NTP / NAT / bastion
   | eth0  10.10.30.1/24          Default-Switch iface 172.x.x.x (Host mgmt)
   |
Hyper-V vSwitch "Lab_Internal" (Internal, 10.10.30.0/24)
   |                              |
DATA_NODE (Rocky) 10.10.30.116   WINDOWS_NODE (Windows) 10.10.30.100-200
  Caddy :8080, metrics, storage    metrics puller (scheduled)
```

Full detail — addressing table, per-service breakdown, internet path, bastion path, and SSH trust — lives in [`network-diagram.md`](./network-diagram.md).

---

## Hosts

| Host           | OS          | Lab IP                  | Role                                                          |
|----------------|-------------|-------------------------|---------------------------------------------------------------|
| Infra_Node     | Debian      | 10.10.30.1 (static)     | Gateway, DHCP, authoritative DNS, NTP server, NAT router, bastion |
| Data_Node      | Rocky Linux | 10.10.30.116 (reserved) | Storage host, key-only SSH target, metrics producer, web server |
| Windows_Node   | Windows     | 10.10.30.100-200 (DHCP) | Metrics collector (scheduled pull over SSH)                   |
| Hyper-V Host   | Windows     | 10.10.30.2 (static)     | Virtualization host; on Lab_Internal but does not route       |
| Host workstation | Windows   | (off-segment)           | Physical admin box; reaches the lab only via the bastion      |

Internal domain: **`squadron.internal`**. DHCP pool: **10.10.30.100–.200**, 12h lease. Data_Node is pinned to **.116** by reservation.

---

## Prerequisites

- A Hyper-V host with an **Internal** virtual switch named `Lab_Internal` (subnet 10.10.30.0/24) and an uplink path to the internet (the "commercial" NIC).
- Three VMs: Debian (Infra), Rocky Linux (Data), Windows (Windows_Node). Generation 2 VMs boot UEFI — ensure the install ISO is UEFI-bootable and boot order lists the DVD first.
- Console access to each VM (the initial build happens before any network path exists).
- The Infra_Node has a **second adapter on the Hyper-V Default Switch** (172.x.x.x) so the physical Host can reach it before the internal network is routable. This address is NAT'd and may change across host reboots.

---

## Setup order

The order matters — several steps depend on the one before, and doing them out of order turns a task into a recovery exercise.

1. **Infra_Node addressing** — static `10.10.30.1/24` on eth0 (Lab_Internal).
2. **DHCP + DNS** — build/configure dnsmasq to serve the pool and resolve `squadron.internal`.
3. **NAT + forwarding** — enable IP forwarding and nftables masquerade so the lab reaches the internet.
4. **NTP** — chrony syncs upstream and serves the lab; block outbound udp/123 for lab clients.
5. **Key-only SSH** — authorize keys on the Data_Node, verify key auth works, *then* disable passwords.
6. **Storage, users, monitoring** — Data_Node disks/users; metrics daemon; Windows scheduled pull.
7. **Web service** — Caddy on the Data_Node, port 8080, reachable off-box.
8. **Bastion access** — Host key path to Infra_Node; ProxyJump config; tunnels.
9. **Documentation + secret scan** — network diagram + README kept current; `gitleaks` over full history before closing a phase.

---

## Node configuration

### Infra_Node (Debian)

- **Static IP:** eth0 = `10.10.30.1/24` (systemd-networkd `.network` unit; `[Match] Name=eth0`).
- **dnsmasq** (compiled from source → `/usr/local/sbin/dnsmasq`, run via a custom systemd unit):
  - `interface=eth0`, `bind-interfaces`, `listen-address=10.10.30.1`
  - `dhcp-range=10.10.30.100,10.10.30.200,255.255.255.0,12h`
  - `dhcp-host=<data-node-MAC>,data-node,10.10.30.116` (Data_Node reservation)
  - `dhcp-option=option:router,10.10.30.1`, `option:dns-server,10.10.30.1`, `option:ntp-server,10.10.30.1`
  - `domain=squadron.internal`, `local=/squadron.internal/`, `expand-hosts`
  - `address=/update.microsoft.com/10.10.30.116` — **intentional DNS spoof** (lab exercise), documented so it is not mistaken for a compromise.
- **Routing/NAT** (nftables):
  - `net.ipv4.ip_forward=1` (persistent in `/etc/sysctl.d/`)
  - `ip nat postrouting`: masquerade `10.10.30.0/24` out `<WAN>`
  - `ip filter forward`: allow lab↔WAN (established/related back), **drop forwarded udp/123**
  - Ruleset saved to `/etc/nftables.conf`; `nftables.service` enabled.
- **chrony:** `pool ... iburst` upstream; `allow 10.10.30.0/24`; `local stratum 10`.
- **sshd:** bastion for Host access (installed via `openssh-server`; the Infra_Node is both SSH client and, now, server).

### Data_Node (Rocky Linux)

- **Reserved DHCP address** 10.10.30.116 (NetworkManager client). DNS/NTP/gateway all resolve to 10.10.30.1.
- **Storage:** 4GB disk → `sdb1` ext4 `/mnt/ops_data`, `sdb2` xfs `/mnt/log_data`. Mounted **by UUID** in `/etc/fstab`.
- **Users:** group `cyber_team`; users `alpha`, `bravo`. Shared dir `/mnt/ops_data/shared` set `3770` (SGID + sticky), group `cyber_team`.
- **Caddy:** serves `/var/www/html` on **port 8080 only** (`:8080` site address → binds all interfaces, plain HTTP). SELinux: 8080 labeled `http_port_t`; firewall opens 8080/tcp.
- **SSH:** `PasswordAuthentication no`, key-only. **Three** authorized keys (Infra_Node, Windows_Node, Host workstation). Host keys were regenerated during the bastion exercise (see Known issues).
- **chrony client:** `server 10.10.30.1 iburst` only; public pools removed.
- **metrics-logger.service:** runs `/usr/local/bin/metrics-logger.sh`, appending timestamped CPU/RAM to `/mnt/log_data/metrics.log` every 30s. `Restart=always`, enabled at boot, `RequiresMountsFor=/mnt/log_data`.

### Windows_Node (Windows)

- **DHCP client** of Infra.
- **OpenSSH client** present (capability check recorded — see Conventions).
- **SSH identity:** own ed25519 key pair; public key authorized on the Data_Node. Private key stays on the Windows_Node.
- **IPv6 disabled** on the Lab_Internal adapter — required for the DNS-spoof exercise (the spoof poisons IPv4 only; dual-stack preference could otherwise route around it).
- **Scheduled task `LabOps-PullMetrics`:** every 5 minutes, SSH to the Data_Node, read `/mnt/log_data/metrics.log`, write to `C:\ProgramData\LabOps\`. Runs as the key-owning user so the key resolves under that profile.

### Hyper-V Host

- `vEthernet (Lab_Internal)` set static to **10.10.30.2/24 with blank gateway and DNS** — present for management but never taking a lease or routing/resolving through Infra. Internet/management goes over the separate "commercial" NIC.

---

## Access model (bastion)

The Data_Node is not directly reachable from the physical Host. Access is a single-command jump through the Infra_Node, described once in the Host's `~/.ssh/config`:

```sshconfig
Host infra
    HostName 172.x.x.x            # Infra_Node Default Switch address (may change on host reboot)
    User <infra-user>
    IdentityFile ~/.ssh/id_ed25519

Host data-node
    HostName 10.10.30.116
    User <data-user>
    IdentityFile ~/.ssh/id_ed25519
    ProxyJump infra
```

- **Open a shell on the Data_Node:** `ssh data-node` — jumps through Infra_Node, no interactive hop.
- **View the Data_Node web page from the Host:** `ssh -L 9090:localhost:8080 data-node`, then browse `http://localhost:9090`. The local port forward tunnels Host:9090 → Data_Node:8080 through the bastion.
- **ProxyJump, not agent forwarding** — chosen deliberately; see [Security notes](#security-notes).
- **Agent:** the Host key is passphrase-protected; the OpenSSH Authentication Agent service is enabled (Automatic) so the passphrase is entered once, not per connection.

---

## Services

| Service | Host | Port/Path | Notes |
|---|---|---|---|
| DHCP + DNS | Infra_Node | udp/67-68, udp/53 | dnsmasq; authoritative for `squadron.internal` |
| NTP | Infra_Node | udp/123 | chrony; only internal time source (outbound 123 blocked) |
| NAT gateway | Infra_Node | — | nftables masquerade; sole internet path |
| SSH bastion | Infra_Node | tcp/22 | ProxyJump target for Host → Data_Node |
| Web | Data_Node | tcp/8080 | Caddy, static HTML, plain HTTP |
| Metrics logger | Data_Node | `/mnt/log_data/metrics.log` | systemd service, 30s interval |
| Metrics puller | Windows_Node | `C:\ProgramData\LabOps\` | Scheduled Task, 5 min, over SSH |

---

## Verification

Quick checks that the lab is behaving. Run per node.

**Infra_Node**
```bash
ip -br addr; ip route show default          # eth0 = 10.10.30.1; default via <WAN>
sudo ss -ulpn | grep -E ':67|:53'           # dnsmasq bound to 10.10.30.1 only
sudo nft list ruleset                        # masquerade + forward + udp/123 drop present
chronyc sources -v                           # upstream pool selected (^*)
dig @10.10.30.1 update.microsoft.com +short  # returns 10.10.30.116 (spoof active)
cat /var/lib/misc/dnsmasq.leases             # .116 reserved to Data_Node
```

**Data_Node**
```bash
ip route show default                        # default via 10.10.30.1
cat /etc/resolv.conf                         # nameserver 10.10.30.1, search squadron.internal
ping -c3 8.8.8.8; ping -c3 google.com        # NAT + DNS working
chronyc -n sources                           # source = 10.10.30.1
ss -tlnp | grep :8080                        # Caddy on 0.0.0.0:8080
systemctl status metrics-logger.service      # active
```

**Windows_Node**
```powershell
ssh -i $env:USERPROFILE\.ssh\id_ed25519 <user>@10.10.30.116 "tail -5 /mnt/log_data/metrics.log"
Start-ScheduledTask -TaskName "LabOps-PullMetrics"
Get-Content C:\ProgramData\LabOps\metrics.log -Tail 5
```

**Host workstation**
```powershell
ssh -G data-node | Select-String "hostname|proxyjump"   # confirms jump config is read
ssh data-node "hostname"                                 # lands on Data_Node in one command
```

**Proof points captured during the build**
- DHCP DORA: full Discover/Offer/Request/Ack captured on the wire (release the lease first — a renew shows only Request/Ack).
- NTP no-fallback: skew a client clock, `chronyc makestep`, confirm with `chronyc tracking` (Reference ID = 10.10.30.1); outbound udp/123 to a public host times out.
- DNS spoof on the wire: flush the client cache, request `update.microsoft.com:8080`, and find the DNS response packet answering `A 10.10.30.116` in Wireshark.
- SSH audit: `journalctl -u sshd | grep "Accepted publickey"` + `ssh-keygen -lf ~/.ssh/authorized_keys` map each connection to a machine.
- Monitoring survives reboot: `metrics.log` gains newer timestamps after a Data_Node reboot; service is `enabled`.
- Secret scan: `gitleaks detect` over full history returns clean (exit 0) before the phase closes.

---

## Operations

**Release/renew a lease (Data_Node, NetworkManager):**
```bash
sudo nmcli device disconnect <iface> && sudo nmcli device connect <iface>
```

**Force a reserved IP back after a lease drifts:** clear the stale lease on the Infra_Node, then renew the client.
```bash
# Infra_Node
sudo systemctl stop dnsmasq
sudo sed -i '/10.10.30.117/d' /var/lib/misc/dnsmasq.leases   # remove the drifted lease
sudo systemctl start dnsmasq
# Data_Node: disconnect/connect the interface
```

**Restart core services (Infra_Node):**
```bash
sudo systemctl restart dnsmasq chrony nftables
```

**Watch DHCP/DNS activity live (Infra_Node):**
```bash
journalctl -u dnsmasq -f
```

**Packet capture (Infra_Node):**
```bash
sudo tcpdump -i eth0 -n -w /tmp/capture.pcap 'udp port 67 or udp port 68 or udp port 53'
```

**Add an SSH identity to the Data_Node:** append the new public key to `~/.ssh/authorized_keys` with a descriptive `-C` comment naming its machine, and add a row to the SSH trust table in `network-diagram.md`.

**After regenerating a host's SSH host keys:** every client that pinned the old key must clear it (`ssh-keygen -R <host>`) before it will reconnect.

**Recover a node that drops to an emergency shell (bad `/etc/fstab`):** an unresolvable UUID or bad mount option fails a boot-time mount and stops boot. Recover in place — don't roll back a snapshot unless a second mistake forces it.

1. Before rebooting into a change, know your recovery path: `passwd -S root` shows `P` (usable root password → emergency-mode prompt works) or `L` (locked → recover via the kernel command line with `rd.break` at the GRUB `e` menu instead).
2. At the shell, root is read-only. Remount it writable — `mount -o remount,rw /` (emergency mode) or `mount -o remount,rw /sysroot && chroot /sysroot` (rd.break).
3. Fix `/etc/fstab` against the real UUID from `blkid`, then validate with `mount -a` (no output = correct).
4. Reboot. Confirm with `df -h /mnt/ops_data /mnt/log_data` and `systemctl status metrics-logger.service`.

A dependent system may surface this as its *own* error — e.g. the Windows_Node puller reports an SSH connection failure, not "the Data_Node is down." Read the upstream cause, not the downstream complaint.

---

## Troubleshooting

| Symptom | Likely cause | Where to look |
|---|---|---|
| A machine that shouldn't be on the lab pulls a 10.10.30.x lease and loses internet/DNS | It has an adapter on Lab_Internal and took a lease; DNS/gateway repointed to 10.10.30.1 | `cat /var/lib/misc/dnsmasq.leases`; set that adapter static with blank gateway/DNS, or move switch to Private |
| Lab nodes get an IP but can't reach the internet | IP forwarding off, or NAT on the wrong interface | `sysctl net.ipv4.ip_forward`; `nft list ruleset` — masquerade must be on `<WAN>` |
| `ping 8.8.8.8` works but `google.com` doesn't | DNS, not routing | `/etc/resolv.conf` should point at 10.10.30.1; check dnsmasq |
| Client won't take time from Infra / "Not synchronised" after skew | chrony won't step a large offset unattended | `chronyc makestep`; confirm source reachable with `chronyc -n sources` |
| `apt`/download fails on Infra during build | No outbound path yet, or empty sources | Infra needs its `<WAN>` NIC up; check `/etc/apt/sources.list` |
| `dig`/`apt install dig` not found | `dig` ships inside `dnsutils`/`bind9-dnsutils`, not a `dig` package | `sudo apt install dnsutils` (or `bind9-dnsutils`) |
| Windows scheduled task runs but log stays empty | Script error (e.g. reserved `$host` variable), or key not found under the task's account | Add error logging to the pull script; confirm task runs as the key-owning user |
| DNS spoof "doesn't work" from Windows | IPv6 undercutting the IPv4 poison, or a cached answer | Disable IPv6 on the Lab adapter; `ipconfig /flushdns` before testing |
| `Invoke-WebRequest` fails on Server Core | Windows PowerShell parses with the (absent) IE engine | Add `-UseBasicParsing` — the error names the parameter |
| `ssh`/`scp` refused on a host | `sshd` not installed/running on that host | `systemctl status ssh` (Debian) / `Get-Service sshd` (Windows) |
| `ssh data-node` → "Could not resolve hostname infra" | ProxyJump references a `Host infra` block that is missing/mis-named | Add the `infra` block; `ssh -G data-node` to confirm it resolves |
| SSH config ignored entirely | File saved as `config.txt`, not `config` | `Get-ChildItem ~/.ssh`; rename to `config` (no extension); verify with `ssh -G` |
| Passphrase prompt on every SSH connection | OpenSSH agent service disabled (ships Disabled on Windows) | `Set-Service ssh-agent -StartupType Automatic; Start-Service ssh-agent; ssh-add` |
| Client refuses to connect after host-key change | Pinned host key changed (`accept-new` won't rescue a *changed* key) | `ssh-keygen -R <host>`, reconnect, verify new fingerprint |
| PowerShell mangles a Windows path with `\\` | Inline `$env:` expansion quoting | Use `Join-Path`, or `cd` and pass a relative path |
| Data_Node drops to emergency shell at boot | Bad UUID / typo in `/etc/fstab` | Remount root rw (`mount -o remount,rw /`), fix fstab, `mount -a`, reboot |

---

## Known issues

Recorded incidents and their resolutions, so the same failure is recognized next time.

| Date | Item | Status |
|---|---|---|
| 2026-09-03 | **Data_Node SSH host keys regenerated.** Any client that pinned the old host key refuses to reconnect with `REMOTE HOST IDENTIFICATION HAS CHANGED`. `accept-new` rescues only a *missing* key, not a *changed* one. Fix: `ssh-keygen -R <host>` on each client (including the Windows_Node's puller account), then reconnect and verify the new fingerprint. An unexpected host-key change in the wild is a possible interception indicator. | Resolved |
| 2026-09-03 | **fstab recovery drill.** A deliberate bad UUID on `/mnt/ops_data` dropped the Data_Node to an emergency shell. Recovered (not rolled back) by remounting root read-write and correcting the UUID. Note: emergency mode needs a root password; if root is locked, recover via the kernel command line (`rd.break`) instead — check `passwd -S root` *before* rebooting. | Resolved |
| 2026-09-03 | **gitleaks history scan.** Record the result each phase: date, gitleaks version, HEAD sha, exit code. Clean = exit 0. A finding is a *live* credential — rotate it first, purge it from history with `git filter-repo` (deleting the file in a new commit does not remove it), re-scan, and log the episode here. | Ongoing |

---

## Conventions

- **Internal domain:** `squadron.internal` (IANA-reserved `.internal`, chosen over `.local` to avoid mDNS conflicts).
- **Addressing:** Infra `.1`, Hyper-V host `.2`, DHCP pool `.100–.200`, Data_Node reserved `.116`. Statics/reservations documented in the diagram.
- **Mounts:** always by **UUID** in fstab, never `/dev/sdX` (device names can reorder across boots).
- **SSH keys:** ed25519; every key carries a `-C` comment naming its source machine (e.g. `windows-node -> data-node`). Private keys never leave their machine — only public keys are copied. Public keys are moved by `scp`/read-aloud, never by copying a private key.
- **SSH config:** one `config` file (no extension) on the Host; the bastion hop lives there as `ProxyJump`, not as an alias or wrapper script. Verify parsing with `ssh -G <host>`.
- **OpenSSH client check (Windows), recorded:**
  ```powershell
  Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Client*'
  ```
- **Firewall block before proof:** enforce the NTP outbound block before demonstrating the client syncs, so the demonstration is proof and not coincidence.
- **Intentional artifacts are labeled:** the `update.microsoft.com` spoof is a deliberate exercise and is called out in both docs so it is never mistaken for a compromise.
- **Secret hygiene:** run `gitleaks detect` over full history before considering a phase closed; record the result in Known issues.
- **Documentation discipline:** update `network-diagram.md` and this README in the same commit as any change to addressing, roles, services, switches, the internet path, the access model, or SSH trust.

---

## Security notes

**Why ProxyJump instead of agent forwarding.** The Host reaches the Data_Node through the Infra_Node bastion using SSH `ProxyJump`, not agent forwarding, and this is deliberate:

- **Agent forwarding (`-A`)** exposes the Host's ssh-agent socket *on the bastion*. Anyone with root on the bastion — or malware there — can use the forwarded agent to authenticate **as the Host** to anything its keys unlock, for as long as the session is open. The bastion is the exposed, higher-risk machine, so handing it live use of your credentials is exactly backwards.
- **ProxyJump (`-J` / `ProxyJump`)** never exposes the agent to the bastion. The bastion only forwards encrypted TCP; the Host authenticates to the Data_Node end-to-end, tunneled through the bastion, which sees only ciphertext and cannot use the Host's keys.

The bastion is a transport, not a trusted party. ProxyJump keeps it that way.

---

## Related documents

- [`network-diagram.md`](./network-diagram.md) — topology, full addressing table, per-service detail, internet path, bastion path, SSH trust, and change log.
