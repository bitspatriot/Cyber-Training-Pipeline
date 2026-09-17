# Task 5.1: Cloud Provisioning & Free DNS

*** Create Oracle Cloud (Free Tier) signup ***
1. Go to https://www.oracle.com/cloud/free/ and sign up
    - Home Region: East Region (us-ashburn-1)
    - Creidt card required for verification, but not charged (never choose to upgrade)

*** Create deSEC account (Free Tier) ***
1. Go to https://desec.io/ → sign up (free)
   - Select deDYN account, and not managed account
2. Create yourname.dedyn.io domain
3. Generate API Token: Account → Token Management → Create Token ("+" button)
   - Create token name
   - Toggle all three radio buttons ("Can create domains," "Can delete domains," and "Can manage tokens" (in Advanced Settings))
4. Save it securely: (the secret is only displayed once, so make sure it's saved securely, and never upload it to GitGub)

*** Install Terraform on the Host ***
1. Host Powershell: winget install HashiCorp.Terraform
2. Verify the install: 
   - Close + Reopen Powershell
   - terraform version

*** Install Oracle Cloud CLI (OCI CLI) on Host ***
1. winget install Oracle.OCI-CLI

*** Gather the Oracle API credentials Terraform needs ***
1. Find Tenancy OCID, User OCID (from the console: Profile → your user, and Tenancy details)
2. Region: us-ashburn-1

*** OCI Console: Generate API Key ***
1. Log into the OCI console
2. Click your profile icon (top-right) → My profile ("User settings")
3. In the left panel under Resources, click API keys → Add API key
4. Select "Generate API key pair"
5. Click Download private key — save it somewhere safe on the Host, e.g. C:\Users\<you>\.oci\oci_api_key.pem. This is the only time you can download it. (Optionally download the public key too, but Oracle keeps it so you won't have to upload it manually.)
6. Click Add
7. Oracle then displays a Configuration file preview (Copy the block and save it for Terraform)

*** Generate the Terraform files needed for configuration and validate the configuration ***
1. Terafform Files Needed:
   - maint.tf
   - terraform.tfvars
   - .gitignore
   - NOTE 1: Terraform configuration files uploaded to repository directory: 06_IaC_Cloud_PKI
   - NOTE 2: Terraform config must resolve Windows path's with "/" instead of "\". Errors will occure during initialization and validation steps if in cannot resolve Host paths.
2. Input the values from Oracle Cloud and Host that Terraform needs for API
3. From repository directory, validate Terraform configuration (from Host Powershell Terraform folder):
   - terraform init (should see message: "Terraform has been successfully initialized!")
   - terraform validate (should see "Success! The configuration is valid.")
   - terraform plan (should output entire Terraform configuration/plan)

*** Set ssh_ingress_cidr to public IP so SSH isn't open to the entire internet ***
1. Find public IP for workstation: https://www.whatismyip.com
2. In terraform.tfvars: set ssh_ingress.cidr to public IP. Don't forget to add CIDR notation (e.g. "/32" at the end of the IP)

*** Apply the Terraform config and build the A1 instance ***
1. Powershell: terraform apply
2. Capture the outputs:
   - availability_domain_used = "DdMo:US-ASHBURN-AD-1"
   - instance_public_ip = "132.145.191.118"
   - instance_shape = "VM.Standard.A1.Flex
3. Connect to new Oracle Cloud Ubuntu instance:
   - ssh -i C:/Users/sandbox_user/<ssh key path> ubuntu@<public-ip>
   - From Host: ssh -i $env:USERPROFILE\.ssh\id_ed25519 ubuntu@132.145.191.118
     - Should authenticate to OCI instance
4. Open terraform.tfstate in a text editor to see all the VM's details that were deployed


