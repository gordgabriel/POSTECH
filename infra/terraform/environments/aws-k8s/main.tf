terraform {
  required_version = ">= 1.3.0"

  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  name         = "${var.project_name}-${var.environment}"
  lab_role_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/LabRole"
}

data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

module "vpc" {
  source = "../../modules/vpc"

  name                 = local.name
  vpc_cidr             = var.vpc_cidr
  public_subnet_count  = 2
  private_subnet_count = 2
  enable_nat_gateway   = false

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_ec2_tag" "cluster" {
  count = length(concat(module.vpc.public_subnet_ids, module.vpc.private_subnet_ids))

  resource_id = concat(module.vpc.public_subnet_ids, module.vpc.private_subnet_ids)[count.index]
  key         = "kubernetes.io/cluster/${local.name}"
  value       = "shared"
}

resource "aws_ec2_tag" "public_load_balancer" {
  count = length(module.vpc.public_subnet_ids)

  resource_id = module.vpc.public_subnet_ids[count.index]
  key         = "kubernetes.io/role/elb"
  value       = "1"
}

resource "aws_ec2_tag" "internal_load_balancer" {
  count = length(module.vpc.private_subnet_ids)

  resource_id = module.vpc.private_subnet_ids[count.index]
  key         = "kubernetes.io/role/internal-elb"
  value       = "1"
}

resource "aws_eks_cluster" "main" {
  name     = local.name
  role_arn = local.lab_role_arn
  version  = var.kubernetes_version

  access_config {
    authentication_mode                         = "API_AND_CONFIG_MAP"
    bootstrap_cluster_creator_admin_permissions = true
  }

  vpc_config {
    subnet_ids = concat(module.vpc.public_subnet_ids, module.vpc.private_subnet_ids)

    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = var.cluster_endpoint_public_access_cidrs
  }

  depends_on = [aws_ec2_tag.cluster]
}

resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${local.name}-workers"
  node_role_arn   = local.lab_role_arn
  subnet_ids      = module.vpc.public_subnet_ids
  instance_types  = [var.node_instance_type]
  capacity_type   = "ON_DEMAND"

  scaling_config {
    desired_size = var.node_desired_size
    min_size     = var.node_min_size
    max_size     = var.node_max_size
  }

  update_config {
    max_unavailable = 1
  }
}

resource "aws_security_group" "database" {
  name        = "${local.name}-postgres"
  description = "Allow PostgreSQL only from the EKS cluster security group"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description     = "PostgreSQL from EKS workloads"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_eks_cluster.main.vpc_config[0].cluster_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_subnet_group" "main" {
  name       = "${local.name}-postgres"
  subnet_ids = module.vpc.private_subnet_ids

  tags = {
    Name = "${local.name}-postgres"
  }
}

resource "aws_db_instance" "main" {
  identifier                  = "${local.name}-postgres"
  engine                      = "postgres"
  instance_class              = var.database_instance_class
  allocated_storage           = 20
  max_allocated_storage       = 50
  storage_type                = "gp3"
  storage_encrypted           = true
  db_name                     = var.database_name
  username                    = var.database_username
  manage_master_user_password = true
  port                        = 5432

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.database.id]
  publicly_accessible    = false
  multi_az               = false

  backup_retention_period    = 1
  auto_minor_version_upgrade = true
  deletion_protection        = false
  skip_final_snapshot        = true
}