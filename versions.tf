terraform {
  required_version = ">= 1.5.0"

  required_providers {
    cloudflare = {
      source  = "registry.terraform.io/cloudflare/cloudflare"
      version = "~> 5.13"
    }
    local = {
      source  = "registry.terraform.io/hashicorp/local"
      version = "~> 2.5"
    }
  }

  # Optional: point at Terraform Cloud later.
  # cloud {
  #   organization = "your-tfc-org"
  #   workspaces { name = "terraform-cloudflare-inverter-gateway" }
  # }
}
