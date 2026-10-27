variable "project_name" {
  description = "Prefix for resources created by this environment."
  type        = string
  default     = "postech"
}

variable "environment" {
  description = "Environment name used in resource names and tags."
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region for the cluster and database."
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR range for the VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "kubernetes_version" {
  description = "EKS Kubernetes control plane version supported in the selected region."
  type        = string
  default     = "1.34"
}

variable "cluster_endpoint_public_access_cidrs" {
  description = "Public IPv4 CIDRs allowed to reach the EKS Kubernetes API endpoint. Use your IP with /32."
  type        = list(string)
  nullable    = false

  validation {
    condition     = length(var.cluster_endpoint_public_access_cidrs) > 0
    error_message = "Provide at least one trusted CIDR for the EKS public API endpoint."
  }
}

variable "node_instance_type" {
  description = "EC2 instance type used by the EKS managed node group."
  type        = string
  default     = "t3.medium"
}

variable "node_desired_size" {
  description = "Initial number of EKS worker nodes."
  type        = number
  default     = 1
}

variable "node_min_size" {
  description = "Minimum number of EKS worker nodes."
  type        = number
  default     = 1
}

variable "node_max_size" {
  description = "Maximum number of EKS worker nodes."
  type        = number
  default     = 2
}

variable "database_instance_class" {
  description = "RDS instance class for the non-production PostgreSQL database."
  type        = string
  default     = "db.t4g.micro"
}

variable "database_name" {
  description = "Initial PostgreSQL database name."
  type        = string
  default     = "postech"
}

variable "database_username" {
  description = "Master username managed by RDS. Its password is stored by Secrets Manager."
  type        = string
  default     = "postech_admin"
}