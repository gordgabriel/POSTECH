terraform {
  required_version = ">= 1.3.0"

  required_providers {
    kind = {
      source  = "tehcyx/kind"
      version = "~> 0.8.0"
    }
  }
}

provider "kind" {}

locals {
  kubeconfig_path = abspath("${path.module}/kubeconfig")
}

resource "kind_cluster" "postech" {
  name            = "postech-iac"
  wait_for_ready  = true
  kubeconfig_path = local.kubeconfig_path
}

output "cluster_name" {
  description = "Name of the Kind cluster managed by Terraform."
  value       = kind_cluster.postech.name
}

output "kubeconfig_path" {
  description = "Path to the local kubeconfig written by the Kind provider."
  value       = local.kubeconfig_path
}