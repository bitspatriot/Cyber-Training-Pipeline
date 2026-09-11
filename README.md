# Squadron Lab

A self-contained virtual lab on Hyper-V that has grown from a single improvised
network core into a segmented enterprise network with a firewall edge and Active
Directory. Three VLANs are carried as tagged traffic over one virtual switch and
routed by a pfSense appliance that is also the internet edge; a Windows Server
2022 Domain Controller owns DNS and identity for `squadron.internal`; and the
Phase 1 service roles have each been consciously moved or kept.

**Status:** Active · **Last updated:** 2026-09-10 · **Maintainer:** Justin

---

## Table of contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Hosts & addressing](#hosts--addressing)
- [Service roles](#service-roles)
- [VLANs & the trunk](#vlans--the-trunk)
- [Firewall & segmentation](#firewall--segmentation)
- [Access model (bastion)](#access-model-bastion)
- [DNS & time](#dns--time)
- [Reproducing the firewall](#reproducing-the-firewall)
- [Verification](#verification)
- [Known issues](#known-issues)
- [Conventions](#conventions)
- [Related documents](#related-documents)

---

## Overview

The lab is a small enterprise network built to be analyzed and reasoned about.
A pfSense firewall is the edge and the inter-VLAN router; three VLANs segment
Users, Servers, and a DMZ over a single tagged trunk; a Windows Server 2022 DC
provides Active Directory and authoritative DNS for `squadron.internal`; and the
Linux hosts (Debian Infra-Node, Rocky Data-Node) live on the Server segment.

Phase 4 re-architected the Phase 1 design: gateway, NAT, routing, and DHCP moved
to pfSense; DNS authority moved to the DC; time consolidated behind the Infra-Node;
and the administrative entry point (bastion) moved onto the firewall's NAT. The
guiding discipline throughout was migrating live services without losing the
network — building each replacement and verifying it before retiring what it
replaced.

Design goals:
- **Segmentation on shared media** — one switch, VLAN-tagged, routed through a firewall, not three isolated switches.
- **Controlled edge** — a single NATed path to the internet through pfSense; the User subnet cannot reach Server management ports unless explicitly allowed.
- **Native identity** — AD DS + DNS on the DC; the network's naming and (ultimately) authentication are domain-native.
- **One time source, enforced at the edge** — only the Infra-Node reaches public NTP; the DC and members chain to it.
- **Reproducible & maintained** — the firewall config is exported (sanitized) and committed; the diagram and this README are kept current.

---

## Architecture

```
INTERNET ── Hyper-V Default Switch (NAT 172.29.x) ── pfSense WAN (static 172.29.208.50)
                                                          │
                                    pfSense (edge / router / DHCP / firewall)
                                    LAN=VLAN20 .20.1  OPT1=VLAN10 .10.1  OPT2=VLAN30 .40.1
                                                          │ hn1 trunk (tagged 10,20,40 / native 99)
                                        Hyper-V vSwitch "Lab_Internal" (one switch)
        ┌───────────────────────────────┼───────────────────────────────┐
   VLAN20 Servers 10.10.20.0/24    VLAN10 Users 10.10.10.0/24     VLAN30 DMZ 10.10.40.0/24
   (static, no DHCP)               (pfSense DHCP .100-.200)        (empty)
   DC .10 · Data .20 · Infra .30   Win11 endpoint (Task 4.4)
```

Full detail — addressing, trunk config, rules, time hierarchy — is in
[`network-diagram.md`](./network-diagram.md).

---

## Hosts & addressing

| Host | OS / Role | Segment | Address |
|---|---|---|---|
| pfSense | firewall / router / edge | WAN + trunk | WAN `172.29.208.50/20`; LAN `10.10.20.1`, OPT1 `10.10.10.1`, OPT2 `10.10.40.1` |
| Windows_Node (DC) | Win Server 2022, AD DS + DNS | VLAN20 | `10.10.20.10` |
| Data-Node | Rocky Linux, server | VLAN20 | `10.10.20.20` |
| Infra-Node | Debian, time source + bastion | VLAN20 | `10.10.20.30` |
| Win11 endpoint (Task 4.4) | domain-joined workstation | VLAN10 | DHCP `10.10.10.100–200` |
| Host workstation | physical admin box | Default Switch | `172.29.x` (DHCP) |

Domain: **`squadron.internal`**. VLAN20/30 are static-only; VLAN10 is DHCP.

---

## Service roles

The Phase 4 handoff, recorded (every Phase 1 role consciously moved or kept):

| Role | Owner |
|---|---|
| Internet gateway / NAT | pfSense (edge) |
| Inter-VLAN routing | pfSense |
| DHCP (VLAN10 only) | pfSense |
| DNS for `squadron.internal` | Domain Controller (`10.10.20.10`) |
| Authoritative time | Infra-Node (`10.10.20.30`) |
| Bastion / SSH entry | Infra-Node, via pfSense NAT (WAN:2222) |

**Retired in Phase 4:** dnsmasq (DHCP + DNS); Infra-Node's second adapter + Phase 1
nftables NAT/forwarding; the `10.10.30.0/24` internal range; the Phase 2
`update.microsoft.com` DNS spoof (died with dnsmasq).

---

## VLANs & the trunk

One Hyper-V virtual switch (`Lab_Internal`), segmented by VLAN tag:

- **VLAN10 Users** `10.10.10.0/24` — pfSense DHCP
- **VLAN20 Servers** `10.10.20.0/24` — static only
- **VLAN30 DMZ** `10.10.40.0/24` — no hosts yet

pfSense's LAN adapter is a **trunk** carrying tagged `10,20,40` with native VLAN
`99` (unused). Each server VM's adapter is **access mode** on VLAN20. Hardware
checksum offload is disabled on the Hyper-V adapters (a Hyper-V requirement, or
traffic behaves erratically in ways that mimic firewall/routing bugs).

> **Trunk gotcha:** re-running `Set-VMNetworkAdapterVlan -NativeVlanId` on an
> existing trunk can append rather than replace, creating a duplicate VLAN in the
> allowed list (`20,10,20,40`) that silently breaks that VLAN while every
> per-endpoint check looks correct. Reset with `-Untagged`, then re-apply once.

---

## Firewall & segmentation

**Constraint:** VLAN10 (Users) cannot initiate to VLAN20 (Servers) management
ports (SSH/RDP) unless explicitly allowed.

- Port alias `mgmt_ports` = `22, 3389`.
- **OPT1 (VLAN10)** rules, top-down (first-match):
  1. Block OPT1 net → LAN net on `mgmt_ports`
  2. Pass OPT1 net → any
- **LAN (VLAN20):** default allow (pfSense hangs anti-lockout + the default rule on
  whatever is named LAN — which is why LAN = VLAN20, the segment with all existing hosts).
- **OPT2 (VLAN30):** deny-all (empty).

**NTP control at the edge** (re-implemented from Phase 1): Pass `10.10.20.30` →
udp/123 *first* (the time source exemption), then Block internal → udp/123. The
exemption is required because pfSense — unlike the old nftables FORWARD chain —
would otherwise strangle the Infra-Node's own upstream sync.

---

## Access model (bastion)

The Data-Node/Infra-Node are not directly reachable from the physical Host. Access
is through the Infra-Node bastion, reached via a pfSense NAT port-forward:

```
Host (Default Switch 172.29.x)
   └─ ssh -p 2222 <infra-user>@172.29.208.50   (pfSense WAN)
        └─ NAT :2222 → 10.10.20.30:22 → Infra-Node
```

Three pfSense changes make this work (the Host's `172.29.x` source is RFC1918):
1. WAN **"Block private networks" unchecked**
2. NAT port-forward WAN:2222 → `10.10.20.30:22`
3. the associated WAN pass rule

The Phase 2 ProxyJump-to-Data-Node pattern can be layered on this new bastion
address; the entry point is now the Infra-Node at `10.10.20.30` via WAN:2222.

---

## DNS & time

**DNS:** the DC is authoritative for `squadron.internal` (forward zone + reverse
zone `10.10.20.0/24`), forwards external queries to `8.8.8.8`/`1.1.1.1`, and both
Linux hosts are registered (forward A + reverse PTR). Every VLAN20 host resolves
against the DC; VLAN10 clients get the DC as DNS via DHCP. `.internal` was chosen
over `.local`, and the domain is the same one dnsmasq served in Phase 1 — a handoff
of authority, not a rename.

**Time:** `members → DC (10.10.20.10) → Infra-Node (10.10.20.30) → public NTP`.
The Infra-Node is the only host permitted outbound on udp/123. The DC's Hyper-V
time-integration service and `VMICTimeProvider` are disabled so it obeys the
Infra-Node rather than silently syncing to the hypervisor clock.

---

## Reproducing the firewall

The pfSense configuration is exported and committed so a teammate can import the
ruleset without touching the GUI.

- Export: **Diagnostics → Backup & Restore → Download configuration as XML**.
- **Sanitize before committing:** the raw `config.xml` contains the webConfigurator
  private key, the admin password hash, and the SNMP community string — strip these.
  The interfaces, VLANs, DHCP scopes, NAT entries, and rules (the reproducible part)
  are safe to publish.
- The phase's gitleaks gate will catch unstripped secrets; sanitize first.

The sanitized `config.xml` lives alongside this README in the Phase 4 repo folder.

---

## Verification

**pfSense** (GUI/console): interface assignments show LAN=`hn1.20`, OPT1=`hn1.10`,
OPT2=`hn1.40`; WAN has an address and internet works (`Diagnostics → Ping 8.8.8.8`);
Firewall → Rules/NAT show the segmentation + NTP + bastion rules.

**DC:**
```powershell
Get-ADDomain | Select DNSRoot, NetBIOSName
Get-DnsServerZone | Select ZoneName, IsReverseLookupZone
w32tm /query /source        # 10.10.20.30 (Infra-Node)
dcdiag /q                    # healthy (a fresh single DC may warn on DFSR/replication)
```

**Linux hosts (Data-Node / Infra-Node):**
```bash
ip -br addr ; ip route                 # single default via 10.10.20.1
cat /etc/resolv.conf                    # nameserver 10.10.20.10
nslookup squadron.internal ; nslookup google.com
chronyc sources -v                      # Infra-Node: ^* upstream; others via DC
```

**Segmentation & controls:**
- From a VLAN10 host: SSH/RDP to a VLAN20 host is blocked; internet works.
- From the Data-Node: `sudo chronyd -Q -t 5 'server pool.ntp.org iburst'` times out (public NTP blocked).
- From the Infra-Node: `chronyc sources` shows `^*` upstream (exempted).
- From the Host: `ssh -p 2222 <infra-user>@172.29.208.50` reaches the Infra-Node.

---

## Known issues

| Item | Status |
|---|---|
| pfSense WAN won't pull DHCP from the Hyper-V Default Switch (layer-2/routing fine; only the DHCP handshake fails — static works). Worked around with static WAN `172.29.208.50/20`. Revisit: reconcile checksum-offload (GUI vs host-side) and/or Default Switch DHCP. | Deferred — end of phase |
| Default Switch subnet changes on host reboot → static WAN may need updating until DHCP is fixed. WAN gateway monitor set to `8.8.8.8` (NAT gateway ignores ping, else pfSense marks WAN down). | Tracked |
| Fresh single DC: `dcdiag` DFSREvent warning — SYSVOL/NETLOGON shared, no 50xx errors; normal first-DC initialization noise. | Benign |

---

## Conventions

- **One switch, VLAN-tagged.** All segmentation is via VLAN tags on `Lab_Internal`; never separate switches.
- **VLAN20 is static by hand** and resolves against the DC (`10.10.20.10`). VLAN10 is DHCP (DC handed out as DNS).
- **LAN = VLAN20** in pfSense (the anti-lockout/default-allow interface must be the one holding the existing hosts).
- **Interface identity by MAC.** Disambiguate WAN vs LAN and duplicate-named vNICs by MAC, never by assuming enumeration order. Rename Hyper-V adapters to unique names when a VM has two.
- **Static-before-retag.** Give a VLAN20 host its static address (from the VM console) and verify *before* changing its VLAN tag — retag first and it lands on the new segment with a dead lease and no way back but the console.
- **Build the new path before retiring the old.** Migrations (bastion, DNS, gateway) build and verify the replacement before removing what it replaces; keep the VM console open as the fallback.
- **`.internal`, not `.local`.** IANA-reserved; avoids mDNS conflicts.
- **Sanitize firewall exports** before committing (keys, password hash, SNMP community removed).
- **Docs in the same commit as the change** — this README and `network-diagram.md`.

---

## Related documents

- [`network-diagram.md`](./network-diagram.md) — topology, full addressing table, trunk/VLAN config, firewall rules, time hierarchy, and change log.
