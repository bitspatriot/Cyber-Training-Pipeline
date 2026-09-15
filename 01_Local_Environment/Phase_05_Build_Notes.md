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