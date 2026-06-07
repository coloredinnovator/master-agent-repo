# ============================================
# HERMES ECOSYSTEM — Microsoft Azure
# ============================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.80"
    }
  }

  backend "azurerm" {
    resource_group_name  = "hermes-state-rg"
    storage_account_name = "hermestfstate"
    container_name       = "tfstate"
    key                  = "azure.terraform.tfstate"
  }
}

variable "location" {
  default = "East US"
}

variable "environment" {
  default = "dev"
}

provider "azurerm" {
  features {}
}

# ==========================================
# Resource Group
# ==========================================
resource "azurerm_resource_group" "hermes" {
  name     = "hermes-${var.environment}-rg"
  location = var.location

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# ==========================================
# Storage Account (GCS / S3 equivalent)
# ==========================================
resource "azurerm_storage_account" "cleanup" {
  name                     = "hermescleanup${var.environment}"
  resource_group_name      = azurerm_resource_group.hermes.name
  location                 = azurerm_resource_group.hermes.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"

  blob_properties {
    versioning_enabled = true
  }

  tags = {
    Environment = var.environment
  }
}

resource "azurerm_storage_container" "data" {
  name                  = "hermes-data"
  storage_account_name  = azurerm_storage_account.cleanup.name
  container_access_type = "private"
}

# ==========================================
# Azure Database for PostgreSQL Flexible Server
# ==========================================
resource "azurerm_postgresql_flexible_server" "hermes" {
  name                   = "hermes-pg-${var.environment}"
  resource_group_name    = azurerm_resource_group.hermes.name
  location               = azurerm_resource_group.hermes.location
  version                = "15"
  administrator_login    = "hermes"
  administrator_password = "CHANGE_ME_IMMEDIATELY"
  sku_name               = "B_Standard_B1ms" # Burstable (cheapest)
  storage_mb             = 32768
  zone                   = "1"

  tags = {
    Environment = var.environment
  }
}

resource "azurerm_postgresql_flexible_server_database" "hermes_db" {
  name      = "hermes_db"
  server_id = azurerm_postgresql_flexible_server.hermes.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.hermes.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# ==========================================
# Azure Container Instances (Cloud Run / Fargate equivalent)
# ==========================================
resource "azurerm_container_group" "hermes" {
  name                = "hermes-agent"
  location            = azurerm_resource_group.hermes.location
  resource_group_name = azurerm_resource_group.hermes.name
  os_type             = "Linux"
  ip_address_type     = "Public"
  dns_name_label      = "hermes-agent-${var.environment}"
  restart_policy      = "Always"

  container {
    name   = "hermes"
    image  = "hermes-agent:latest"
    cpu    = "1"
    memory = "1.5"

    ports {
      port     = 8080
      protocol = "TCP"
    }

    environment_variables = {
      PORT           = "8080"
      POSTGRES_HOST  = azurerm_postgresql_flexible_server.hermes.fqdn
      POSTGRES_PORT  = "5432"
      POSTGRES_DB    = "hermes_db"
      LLM_PROVIDER   = "ollama"
    }

    secure_environment_variables = {
      POSTGRES_USER     = "hermes"
      POSTGRES_PASSWORD = "CHANGE_ME_IMMEDIATELY"
    }

    liveness_probe {
      http_get {
        path   = "/health"
        port   = 8080
        scheme = "Http"
      }
      initial_delay_seconds = 15
      period_seconds        = 20
    }

    readiness_probe {
      http_get {
        path   = "/health"
        port   = 8080
        scheme = "Http"
      }
      initial_delay_seconds = 5
      period_seconds        = 10
    }
  }

  tags = {
    Environment = var.environment
  }
}

# ==========================================
# Log Analytics Workspace (Cloud Logging equivalent)
# ==========================================
resource "azurerm_log_analytics_workspace" "hermes" {
  name                = "hermes-logs-${var.environment}"
  location            = azurerm_resource_group.hermes.location
  resource_group_name = azurerm_resource_group.hermes.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

# ==========================================
# Outputs
# ==========================================
output "container_fqdn" {
  value = azurerm_container_group.hermes.fqdn
}

output "postgres_fqdn" {
  value = azurerm_postgresql_flexible_server.hermes.fqdn
}

output "storage_account" {
  value = azurerm_storage_account.cleanup.name
}
