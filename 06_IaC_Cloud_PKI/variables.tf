# ============================================================================
# Variable declarations. Real values go in terraform.tfvars (GITIGNORED).
# main.tf references these so main.tf itself carries no secrets and is safe to
# commit.
# ============================================================================

# --- OCI authentication (from your API key config preview) -------------------
variable "tenancy_ocid" {
  type        = string
  description = "Tenancy OCID (ocid1.tenancy.oc1..)."
}

variable "user_ocid" {
  type        = string
  description = "User OCID (ocid1.user.oc1..)."
}

variable "fingerprint" {
  type        = string
  description = "API signing key fingerprint."
}

variable "private_key_path" {
  type        = string
  description = "Path to the API signing PRIVATE key on the workstation (use forward slashes on Windows)."
}

variable "region" {
  type        = string
  description = "Home region, e.g. us-ashburn-1."
}

# --- Compartment -------------------------------------------------------------
# For a simple free-tier setup you can use the tenancy (root compartment) OCID
# here as well. Set to a child compartment OCID if you created one.
variable "compartment_ocid" {
  type        = string
  description = "Compartment OCID to create resources in (root/tenancy OCID is fine for free tier)."
}

# --- Availability domain selector -------------------------------------------
variable "ad_number" {
  type        = number
  description = "Which availability domain (1, 2, or 3). Change and retry on out-of-capacity errors."
  default     = 1
}

# --- Networking --------------------------------------------------------------
variable "vcn_cidr" {
  type        = string
  description = "VCN CIDR block."
  default     = "10.20.0.0/16"
}

variable "subnet_cidr" {
  type        = string
  description = "Subnet CIDR block (within the VCN)."
  default     = "10.20.10.0/24"
}

variable "ssh_ingress_cidr" {
  type        = string
  description = "CIDR allowed to reach SSH (22). Set to your workstation's public IP as x.x.x.x/32 for hygiene, or 0.0.0.0/0 to allow anywhere."
  default     = "0.0.0.0/0"
}

# --- Compute shape (PINNED to Always-Free A1) --------------------------------
# Do NOT change these to a larger size — anything above 2 OCPU / 12 GB total is
# NOT Always-Free-eligible, whatever the console lets you pick.
variable "instance_shape" {
  type        = string
  description = "Instance shape. Always-Free ARM = VM.Standard.A1.Flex. Do not use x86 micro (too little RAM for the stack)."
  default     = "VM.Standard.A1.Flex"
}

variable "instance_ocpus" {
  type        = number
  description = "OCPUs. Always-Free A1 ceiling is 2 total across all instances (halved from 4 in June 2026)."
  default     = 2
}

variable "instance_memory_gb" {
  type        = number
  description = "Memory in GB. Always-Free A1 ceiling is 12 total (halved from 24 in June 2026)."
  default     = 12
}

variable "ubuntu_version" {
  type        = string
  description = "Ubuntu version for the image lookup."
  default     = "22.04"
}

variable "ssh_public_key_path" {
  type        = string
  description = "Path to the workstation's SSH PUBLIC key to authorize on the VM (forward slashes on Windows)."
}
