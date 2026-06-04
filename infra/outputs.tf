# ~/korrelate/infra/outputs.tf
output "kubeconfig_command" {
  value = "aws eks update-kubeconfig --name ${var.cluster_name} --region ${var.region}"
}
output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}
