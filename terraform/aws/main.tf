# ============================================
# HERMES ECOSYSTEM — Amazon Web Services
# ============================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "hermes-terraform-state"
    key    = "aws/terraform.tfstate"
    region = "us-east-1"
  }
}

variable "region" {
  default = "us-east-1"
}

variable "environment" {
  default = "dev"
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "hermes"
    }
  }
}

# ==========================================
# VPC & Networking
# ==========================================
resource "aws_vpc" "hermes" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = { Name = "hermes-vpc" }
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.hermes.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.region}a"
  map_public_ip_on_launch = true
  tags                    = { Name = "hermes-public-a" }
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.hermes.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "${var.region}b"
  map_public_ip_on_launch = true
  tags                    = { Name = "hermes-public-b" }
}

resource "aws_internet_gateway" "hermes" {
  vpc_id = aws_vpc.hermes.id
  tags   = { Name = "hermes-igw" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.hermes.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.hermes.id
  }
  tags = { Name = "hermes-public-rt" }
}

resource "aws_route_table_association" "a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}

# ==========================================
# Security Groups
# ==========================================
resource "aws_security_group" "hermes_sg" {
  name   = "hermes-sg"
  vpc_id = aws_vpc.hermes.id

  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "db_sg" {
  name   = "hermes-db-sg"
  vpc_id = aws_vpc.hermes.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.hermes_sg.id]
  }
}

# ==========================================
# S3 Bucket (GCS equivalent)
# ==========================================
resource "aws_s3_bucket" "cleanup" {
  bucket = "hermes-cleanup-${var.environment}"
}

resource "aws_s3_bucket_versioning" "cleanup" {
  bucket = aws_s3_bucket.cleanup.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "cleanup" {
  bucket                  = aws_s3_bucket.cleanup.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cleanup" {
  bucket = aws_s3_bucket.cleanup.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

# ==========================================
# RDS PostgreSQL (free tier eligible)
# ==========================================
resource "aws_db_subnet_group" "hermes" {
  name       = "hermes-db-subnet"
  subnet_ids = [aws_subnet.public_a.id, aws_subnet.public_b.id]
}

resource "aws_db_instance" "postgres" {
  identifier             = "hermes-postgres"
  engine                 = "postgres"
  engine_version         = "15.4"
  instance_class         = "db.t3.micro" # Free tier eligible
  allocated_storage      = 20
  storage_encrypted      = true
  db_name                = "hermes_db"
  username               = "hermes"
  password               = "CHANGE_ME_IMMEDIATELY" # Use AWS Secrets Manager in prod
  db_subnet_group_name   = aws_db_subnet_group.hermes.name
  vpc_security_group_ids = [aws_security_group.db_sg.id]
  skip_final_snapshot    = true
  publicly_accessible    = false

  tags = { Name = "hermes-postgres" }
}

# ==========================================
# ECS Fargate (Cloud Run equivalent)
# ==========================================
resource "aws_ecs_cluster" "hermes" {
  name = "hermes-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_task_definition" "hermes" {
  family                   = "hermes-agent"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = "hermes"
    image = "hermes-agent:latest"
    portMappings = [{
      containerPort = 8080
      protocol      = "tcp"
    }]
    environment = [
      { name = "PORT", value = "8080" },
      { name = "POSTGRES_HOST", value = aws_db_instance.postgres.address },
      { name = "POSTGRES_PORT", value = "5432" },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/hermes-agent"
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "hermes"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 15
    }
  }])
}

# ==========================================
# IAM Roles for ECS
# ==========================================
resource "aws_iam_role" "ecs_execution" {
  name = "hermes-ecs-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task" {
  name = "hermes-ecs-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "s3_access" {
  name = "hermes-s3-access"
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
      Resource = [aws_s3_bucket.cleanup.arn, "${aws_s3_bucket.cleanup.arn}/*"]
    }]
  })
}

# ==========================================
# CloudWatch Log Group
# ==========================================
resource "aws_cloudwatch_log_group" "hermes" {
  name              = "/ecs/hermes-agent"
  retention_in_days = 30
}

# ==========================================
# Outputs
# ==========================================
output "rds_endpoint" {
  value = aws_db_instance.postgres.endpoint
}

output "s3_bucket" {
  value = aws_s3_bucket.cleanup.bucket
}

output "ecs_cluster" {
  value = aws_ecs_cluster.hermes.name
}
