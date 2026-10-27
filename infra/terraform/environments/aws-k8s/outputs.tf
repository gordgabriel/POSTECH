output "cluster_name" {
  description = "EKS cluster name."
  value       = aws_eks_cluster.main.name
}

output "cluster_endpoint" {
  description = "Kubernetes API endpoint."
  value       = aws_eks_cluster.main.endpoint
}

output "configure_kubectl" {
  description = "Command to add this cluster to the local kubeconfig."
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${aws_eks_cluster.main.name}"
}

output "database_address" {
  description = "Private DNS address of the PostgreSQL instance."
  value       = aws_db_instance.main.address
}

output "database_port" {
  description = "PostgreSQL port."
  value       = aws_db_instance.main.port
}

output "database_name" {
  description = "Initial PostgreSQL database name."
  value       = aws_db_instance.main.db_name
}

output "database_username" {
  description = "RDS PostgreSQL master username."
  value       = aws_db_instance.main.username
}

output "database_master_secret_arn" {
  description = "Secrets Manager ARN containing the RDS master credentials."
  value       = aws_db_instance.main.master_user_secret[0].secret_arn
}