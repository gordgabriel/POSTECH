terraform {
  required_version = ">= 1.3.0"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.38"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.9"
    }
  }
}

locals {
  kubeconfig_path = abspath("${path.module}/../local-kind/kubeconfig")
}

provider "kubernetes" {
  config_path = local.kubeconfig_path
}

provider "helm" {
  kubernetes = {
    config_path = local.kubeconfig_path
  }
}

resource "helm_release" "metrics_server" {
  name       = "metrics-server"
  namespace  = "kube-system"
  repository = "https://kubernetes-sigs.github.io/metrics-server/"
  chart      = "metrics-server"
  version    = "3.14.0"
  wait       = true
  timeout    = 300

  values = [
    yamlencode({
      args = ["--kubelet-insecure-tls"]
    })
  ]
}

resource "random_password" "database" {
  length  = 40
  special = false
}

resource "random_password" "django" {
  length  = 50
  special = false
}

resource "kubernetes_namespace_v1" "postech" {
  metadata {
    name = "postech"
  }
}

resource "kubernetes_secret_v1" "postech" {
  metadata {
    name      = "postech-secrets"
    namespace = kubernetes_namespace_v1.postech.metadata[0].name
  }

  data = {
    SECRET_KEY        = random_password.django.result
    DB_PASSWORD       = random_password.database.result
    POSTGRES_PASSWORD = random_password.database.result
  }

  type = "Opaque"
}

resource "kubernetes_service_v1" "postgres" {
  metadata {
    name      = "postech-db"
    namespace = kubernetes_namespace_v1.postech.metadata[0].name
    labels = {
      app = "postech-db"
    }
  }

  spec {
    cluster_ip = "None"

    selector = {
      app = "postech-db"
    }

    port {
      name        = "postgres"
      port        = 5432
      target_port = 5432
    }
  }
}

resource "kubernetes_stateful_set_v1" "postgres" {
  metadata {
    name      = "postech-db"
    namespace = kubernetes_namespace_v1.postech.metadata[0].name
  }

  spec {
    service_name = kubernetes_service_v1.postgres.metadata[0].name
    replicas     = 1

    selector {
      match_labels = {
        app = "postech-db"
      }
    }

    template {
      metadata {
        labels = {
          app = "postech-db"
        }
      }

      spec {
        automount_service_account_token = false

        container {
          name              = "postgres"
          image             = "postgres:16-alpine"
          image_pull_policy = "IfNotPresent"

          port {
            name           = "postgres"
            container_port = 5432
          }

          env {
            name  = "POSTGRES_DB"
            value = "postech"
          }

          env {
            name  = "POSTGRES_USER"
            value = "postech_user"
          }

          env {
            name = "POSTGRES_PASSWORD"

            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.postech.metadata[0].name
                key  = "POSTGRES_PASSWORD"
              }
            }
          }

          volume_mount {
            name       = "postgres-data"
            mount_path = "/var/lib/postgresql/data"
          }

          resources {
            requests = {
              cpu               = "100m"
              memory            = "128Mi"
              ephemeral-storage = "256Mi"
            }
            limits = {
              cpu               = "1000m"
              memory            = "512Mi"
              ephemeral-storage = "1Gi"
            }
          }
        }
      }
    }

    volume_claim_template {
      metadata {
        name = "postgres-data"
      }

      spec {
        access_modes = ["ReadWriteOnce"]

        resources {
          requests = {
            storage = "1Gi"
          }
        }
      }
    }
  }

  depends_on = [kubernetes_secret_v1.postech]
}