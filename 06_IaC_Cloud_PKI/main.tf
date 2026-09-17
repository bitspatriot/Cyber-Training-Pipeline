# ============================================================================
# Phase 5 — Oracle Cloud Free Tier: single Always-Free Ampere A1 Ubuntu VM
# inside a VCN, with a Terraform-owned security list opening ONLY 22/80/443.
#
# The security rules live here, not in the console. Every future change to this
# host's network exposure is made HERE and re-applied, never by clicking in the
# web console — a console-only rule exists in nothing you committed.
# ============================================================================

terraform {
  required_version = ">= 1.3.0"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 5.0.0"
    }
  }
}

# --- Provider: authenticates to OCI with your API signing key ---------------
provider "oci" {
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}

# ============================================================================
# Availability domain
# A1 capacity varies by AD; if `apply` returns an out-of-capacity error, switch
# ad_number (1/2/3) and retry. That error is Oracle-side, not a config bug.
# ============================================================================
data "oci_identity_availability_domains" "ads" {
  compartment_id = var.tenancy_ocid
}

locals {
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[var.ad_number - 1].name
}

# ============================================================================
# Networking: VCN -> Internet Gateway -> Route Table -> Security List -> Subnet
# ============================================================================

resource "oci_core_vcn" "phase5_vcn" {
  compartment_id = var.compartment_ocid
  cidr_blocks    = [var.vcn_cidr]
  display_name   = "phase5-vcn"
  dns_label      = "phase5vcn"
}

resource "oci_core_internet_gateway" "phase5_igw" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.phase5_vcn.id
  display_name   = "phase5-igw"
  enabled        = true
}

resource "oci_core_route_table" "phase5_rt" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.phase5_vcn.id
  display_name   = "phase5-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.phase5_igw.id
  }
}

# --- Security list: the Terraform-owned firewall. ONLY 22 / 80 / 443 in. -----
# 22  : SSH, to manage the VM (scoped to your workstation IP by var.ssh_ingress_cidr)
# 80  : HTTP — required for Let's Encrypt http-01 challenge + HTTPS redirect
# 443 : HTTPS — the Caddy reverse proxy (the only container that publishes a port)
# Nothing else: Postgres/API/front-end are internal to the Docker network.
resource "oci_core_security_list" "phase5_sl" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.phase5_vcn.id
  display_name   = "phase5-sl"

  # Egress: allow all outbound (the VM needs to reach Let's Encrypt, apt, Docker Hub, etc.)
  egress_security_rules {
    destination      = "0.0.0.0/0"
    destination_type = "CIDR_BLOCK"
    protocol         = "all"
  }

  # Ingress 22 — SSH. Scope to your workstation IP for hygiene; widen only if needed.
  ingress_security_rules {
    protocol    = "6" # TCP
    source      = var.ssh_ingress_cidr
    source_type = "CIDR_BLOCK"
    description = "SSH from workstation"
    tcp_options {
      min = 22
      max = 22
    }
  }

  # Ingress 80 — HTTP for ACME http-01 + redirect to HTTPS. Must be world-reachable.
  ingress_security_rules {
    protocol    = "6"
    source      = "0.0.0.0/0"
    source_type = "CIDR_BLOCK"
    description = "HTTP (Let's Encrypt http-01 + redirect)"
    tcp_options {
      min = 80
      max = 80
    }
  }

  # Ingress 443 — HTTPS (Caddy). World-reachable.
  ingress_security_rules {
    protocol    = "6"
    source      = "0.0.0.0/0"
    source_type = "CIDR_BLOCK"
    description = "HTTPS (Caddy reverse proxy)"
    tcp_options {
      min = 443
      max = 443
    }
  }
}

resource "oci_core_subnet" "phase5_subnet" {
  compartment_id    = var.compartment_ocid
  vcn_id            = oci_core_vcn.phase5_vcn.id
  cidr_block        = var.subnet_cidr
  display_name      = "phase5-subnet"
  dns_label         = "phase5subnet"
  route_table_id    = oci_core_route_table.phase5_rt.id
  security_list_ids = [oci_core_security_list.phase5_sl.id]

  # Public subnet — the VM gets a public IP so the world can reach 80/443.
  prohibit_public_ip_on_vnic = false
}

# ============================================================================
# Compute: single Always-Free Ampere A1 Ubuntu VM
# Shape is PINNED and verified: VM.Standard.A1.Flex, 2 OCPU / 12 GB.
# This is the ENTIRE Always-Free A1 allocation (halved to 2/12 in June 2026),
# and it is ARM — later container images must be arm64, not x86.
# ============================================================================

# Latest Ubuntu 22.04 ARM (aarch64) image in the region
data "oci_core_images" "ubuntu_arm" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = var.ubuntu_version
  shape                    = var.instance_shape
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

resource "oci_core_instance" "phase5_vm" {
  compartment_id      = var.compartment_ocid
  availability_domain = local.availability_domain
  display_name        = "phase5-vm"
  shape               = var.instance_shape

  # Flex shape sizing — pinned to the Always-Free A1 ceiling (2 OCPU / 12 GB total).
  shape_config {
    ocpus         = var.instance_ocpus
    memory_in_gbs = var.instance_memory_gb
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.phase5_subnet.id
    assign_public_ip = true
    hostname_label   = "phase5vm"
  }

  source_details {
    source_type = "image"
    source_id   = data.oci_core_images.ubuntu_arm.images[0].id
  }

  # Authorize ONLY the workstation's SSH public key. This is the only key the VM
  # accepts — the on-prem Infra-Node bastion has no path in.
  metadata = {
    ssh_authorized_keys = file(var.ssh_public_key_path)
  }
}

# ============================================================================
# Outputs
# ============================================================================
output "instance_public_ip" {
  description = "Public IP of the VM — point your dedyn.io A-record here."
  value       = oci_core_instance.phase5_vm.public_ip
}

output "instance_shape" {
  description = "Confirm this reads VM.Standard.A1.Flex (ARM, Always-Free)."
  value       = oci_core_instance.phase5_vm.shape
}

output "availability_domain_used" {
  value = local.availability_domain
}
