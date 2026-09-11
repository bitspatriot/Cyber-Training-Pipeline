# Squadron Lab — Network Diagram & Reference

**Last updated:** 2026-09-10 (Phase 4: segmentation + identity)
**Maintainer:** Justin
**Status:** Correct as of the date above. Update this file in the same commit as any change to addressing, VLANs, roles, the firewall ruleset, or the internet path.

> A diagram nobody maintains is worse than no diagram, because it is believed.
> Phase 4 changed almost every particular of the Phase 1 design — this document reflects the current (Phase 4) architecture. See the Change log for history.

---

## Topology

Three VLANs are carried as tagged traffic over the single Hyper-V virtual switch
(`Lab_Internal`) and routed between by a pfSense appliance that is also the network
edge. pfSense's WAN sits on the Hyper-V Default Switch (internet path).

```
                               INTERNET
                                   |
                     +-------------------------------+
                     |   Hyper-V "Default Switch"     |  (NAT, 172.29.x/20,
                     |   subnet changes on host reboot|   gateway ignores ping)
                     +-------------------------------+
                                   |
                                   | WAN  (static 172.29.208.50/20)
                                   |      MAC ...74:06
                    +==========================================+
                    |            pfSense (CE)                   |
                    |   edge firewall / NAT / inter-VLAN router |
                    |   DHCP (VLAN10 only) / NTP block+exempt   |
                    |                                          |
                    |   LAN  = VLAN20  hn1.20  10.10.20.1/24    |
                    |   OPT1 = VLAN10  hn1.10  10.10.10.1/24    |
                    |   OPT2 = VLAN30  hn1.40  10.10.40.1/24    |
                    +===================hn1 (trunk)============+
                                   |  MAC ...74:07
                                   |  TRUNK: tagged 10,20,40  native 99
                     +-------------------------------+
                     | Hyper-V vSwitch "Lab_Internal"|  (ONE switch,
                     |  segmented by VLAN tag)       |   VLAN-tagged)
                     +-------------------------------+
             VLAN20 (Servers)        VLAN10 (Users)        VLAN30 (DMZ)
             10.10.20.0/24           10.10.10.0/24         10.10.40.0/24
             no DHCP, all static     pfSense DHCP          (no hosts yet)
                    |                 .100-.200
     +--------------+-----------+          |
     |              |           |          |
 +--------+   +----------+  +--------+  +-----------------+
 | DC     |   | Data-    |  | Infra- |  | Win11 endpoint  |
 | Win2022|   | Node     |  | Node   |  | (Task 4.4)      |
 |.20.10  |   | .20.20   |  | .20.30 |  | DHCP .10.100+   |
 | AD+DNS |   | Rocky    |  | Debian |  | domain-joined   |
 +--------+   +----------+  +--------+  +-----------------+

  Host workstation (Win11, physical) sits on the Default Switch (WAN side),
  reaches the Infra-Node bastion via pfSense NAT:  Host -> pfSense WAN:2222 -> Infra 10.10.20.30:22
```

---

## Addressing table

| Host / Interface        | OS / Role                    | Segment        | Address            | Assigned by      |
|-------------------------|------------------------------|----------------|--------------------|------------------|
| pfSense WAN             | firewall edge                | Default Switch | 172.29.208.50/20 (static) | manual*     |
| pfSense LAN (VLAN20)    | inter-VLAN gateway           | VLAN20         | 10.10.20.1/24      | static           |
| pfSense OPT1 (VLAN10)   | users gateway                | VLAN10         | 10.10.10.1/24      | static           |
| pfSense OPT2 (VLAN30)   | DMZ gateway                  | VLAN30         | 10.10.40.1/24      | static           |
| DC (Windows_Node)       | Win Server 2022, AD DS + DNS | VLAN20         | 10.10.20.10/24     | static           |
| Data-Node               | Rocky Linux, server          | VLAN20         | 10.10.20.20/24     | static           |
| Infra-Node              | Debian, time source + bastion| VLAN20         | 10.10.20.30/24     | static           |
| Win11 endpoint (4.4)    | domain-joined workstation    | VLAN10         | 10.10.10.100-200   | pfSense DHCP     |
| Host workstation        | physical admin box           | Default Switch | 172.29.x (DHCP)    | Default Switch   |

*pfSense WAN is static as a workaround: it would not pull DHCP from the Default
Switch (see Known issues). The Default Switch subnet changes on host reboot, so
the WAN static may need updating after a host reboot until DHCP is fixed.

DHCP: **VLAN10 only**, pool `10.10.10.100–.200`, hands out the DC (`10.10.20.10`)
as DNS. VLAN20 and VLAN30 have **no DHCP** — every VLAN20 host is static by hand
and resolves against the DC.

---

## Service roles (post Phase 4 handoff)

| Role | Owner | Notes |
|---|---|---|
| Internet gateway / NAT | **pfSense** | network edge; automatic outbound NAT for all VLANs |
| Inter-VLAN routing | **pfSense** | routes between VLAN10/20/40 |
| DHCP | **pfSense**, VLAN10 only | VLAN20/30 static |
| DNS for squadron.internal | **DC** (`10.10.20.10`) | forward zone + reverse zone `10.10.20.0/24`; forwards external to 8.8.8.8 / 1.1.1.1 |
| Authoritative time | **Infra-Node** (`10.10.20.30`) | chrony; only host allowed to reach public NTP |
| Bastion / SSH entry | **Infra-Node** | reached from Host via pfSense NAT WAN:2222 → 10.10.20.30:22 |

**Consciously retired in Phase 4:** dnsmasq (DHCP + DNS), the Infra-Node's second
adapter + Phase 1 nftables NAT/forwarding, the old `10.10.30.0/24` internal range,
and the Phase 2 `update.microsoft.com` DNS spoof (died with dnsmasq).

---

## VLAN / trunk configuration

- **One virtual switch** (`Lab_Internal`), segmented by VLAN tag — not three switches.
- pfSense LAN adapter (`hn1`, MAC ...74:07) is a **trunk**: tagged VLANs `10,20,40`, native VLAN `99` (unused dead-end).
  - Hyper-V: `Set-VMNetworkAdapterVlan -Trunk -AllowedVlanIdList "10,20,40" -NativeVlanId 99`
- pfSense WAN adapter (`hn0`, MAC ...74:06) is untagged/access on the Default Switch.
- Each server VM's adapter is **access mode** on its VLAN (all VLAN20: `-Access -VlanId 20`).
- Hardware checksum offload disabled on Hyper-V for these adapters (Hyper-V requirement).

> **Gotcha recorded:** re-running `Set-VMNetworkAdapterVlan -NativeVlanId` on an
> existing trunk can *append* rather than replace, producing a duplicate VLAN in
> the allowed list (e.g. `20,10,20,40`) that silently breaks that VLAN's delivery
> while every per-endpoint check looks correct. Reset with `-Untagged` first, then
> re-apply the full trunk in one command.

---

## Internet path

```
VLAN10 / VLAN20 / VLAN30 hosts
        |  default route -> their pfSense VLAN interface (.1)
        v
pfSense  (inter-VLAN routing + automatic outbound NAT)
        |  WAN  172.29.208.50  ->  Hyper-V Default Switch (NAT)  ->  internet
```

No host has a direct internet path; everything is NATed through pfSense.

---

## Firewall rules (segmentation)

**Constraint:** VLAN10 (Users) must not initiate to VLAN20 (Servers) management
ports (SSH/RDP) unless explicitly allowed.

- Port alias `mgmt_ports` = `22, 3389`.
- **OPT1 (VLAN10)**, in order (first-match, top-down):
  1. **Block** OPT1 net → LAN net, dest port `mgmt_ports` (the constraint)
  2. **Pass** OPT1 net → any (internet + other services)
- **LAN (VLAN20):** default allow (pfSense anti-lockout + default rule; this is why LAN = VLAN20).
- **OPT2 (VLAN30):** empty = deny-all (no hosts yet).

**NTP control (re-implemented from Phase 1, moved to the edge):**
- **Pass** source `10.10.20.30` (Infra-Node) → any udp/123 — *first* (exemption).
- **Block** internal nets → any udp/123 — after.
- The exemption is required because pfSense (unlike the old nftables FORWARD chain)
  would otherwise strangle the time source's own upstream sync.

**Bastion NAT (Host → Infra-Node):**
- WAN "Block private networks" **unchecked** (Host's 172.29.x source is RFC1918).
- NAT port-forward: WAN TCP :2222 → `10.10.20.30:22`, with associated WAN pass rule.

---

## Host access path (bastion)

```
Host workstation (Win11, on Default Switch 172.29.x)
      |  ssh -p 2222 <infra-user>@172.29.208.50   (pfSense WAN)
      v
pfSense  NAT port-forward :2222 -> 10.10.20.30:22
      v
Infra-Node (VLAN20)  — bastion / SSH entry point
```

The Phase 2 ProxyJump-to-Data-Node model can be rebuilt on top of this new bastion
address if desired; the entry point is now the Infra-Node at `10.10.20.30` reached
via pfSense WAN:2222 rather than the old Default-Switch second adapter.

---

## Time hierarchy

```
domain members  ->  DC (10.10.20.10)  ->  Infra-Node (10.10.20.30)  ->  public NTP
                    (AD time hierarchy)    (chrony, only host allowed out on udp/123)
```

- Infra-Node chrony `allow 10.10.20.0/24` (updated from the old `10.10.30.0/24`, which was refusing the moved hosts).
- DC syncs from the Infra-Node via `w32tm /manualpeerlist 10.10.20.30`.
- DC's Hyper-V "Time Synchronization" integration service **disabled**, and the
  `VMICTimeProvider` disabled in the registry — otherwise the DC silently takes the
  hypervisor's clock and ignores the Infra-Node.

---

## DNS

- Authoritative for **`squadron.internal`** on the DC (forward zone + reverse zone `10.10.20.0/24`).
- Both Linux hosts registered (forward A + reverse PTR): `data-node` `10.10.20.20`, `infra-node` `10.10.20.30`.
- DC forwards external queries to `8.8.8.8` / `1.1.1.1`.
- Every VLAN20 host resolves against the DC (`10.10.20.10`); VLAN10 clients get the DC as DNS via DHCP.
- `.internal` chosen over `.local` (IANA-reserved special-use TLD; avoids mDNS conflicts). Same domain dnsmasq served in Phase 1 — this was a handoff of DNS authority, not a rename.

---

## Known issues / deferred

| Item | Status |
|---|---|
| pfSense WAN won't pull DHCP from the Default Switch (layer 2/routing fine, only the DHCP handshake fails; static works). Worked around with static WAN `172.29.208.50/20`. Revisit: reconcile checksum-offload state (GUI checkbox vs host-side) and/or Default Switch DHCP after host reboot. | **Deferred** — end of phase |
| Default Switch subnet changes on host reboot; static WAN may need updating until DHCP is fixed. WAN gateway monitor set to `8.8.8.8` (the NAT gateway ignores ping). | Tracked |
| pfSense DNS Resolver was flaky for VLAN20 clients; mooted now that the DC is the network resolver. | Likely non-issue |

---

## How to keep this correct

Update this file in the same commit as any change to: a VLAN or subnet; a host's
address or role; the trunk/tagging; a firewall rule or NAT entry; the DNS zones or
forwarder; the time hierarchy; the bastion path; or the WAN configuration.

Self-check commands:
```
# pfSense (console/GUI):   interface assignments, Status->Interfaces, Firewall->Rules/NAT
# DC:
Get-ADDomain ; Get-DnsServerZone ; w32tm /query /source ; dcdiag /q
# Data-Node / Infra-Node:
ip -br addr ; ip route ; cat /etc/resolv.conf ; chronyc sources -v
```

---

## Change log

| Date | Change | By |
|------|--------|-----|
| 2026-09-01 | Phase 1: Infra-Node as core (DHCP/DNS/NAT/NTP), key-only SSH, storage/users on Data-Node, metrics pipeline. | Justin |
| 2026-09-03 | Phase 2: reserved IP, Caddy :8080, intentional DNS spoof, bastion/ProxyJump, tunnels, three-key SSH trust. | Justin |
| 2026-09-10 | **Phase 4: full re-architecture.** pfSense edge + 3 VLANs on one trunk (10/20/40). Windows_Node promoted to DC (AD DS + DNS, fwd+reverse zones). Service handoff: gateway/NAT/DHCP/routing → pfSense; DNS → DC; time chain members→DC→Infra→upstream. dnsmasq retired; Infra-Node 2nd adapter + Phase 1 NAT retired; old 10.10.30.0/24 range retired; Phase 2 spoof died. Bastion moved to Infra `10.10.20.30` via pfSense WAN:2222. Segmentation rules (VLAN10 ✗→ VLAN20 mgmt). WAN static workaround for Default-Switch DHCP failure. | Justin |
