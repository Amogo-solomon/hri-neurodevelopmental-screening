###############################################################################
# HRI Behaviour Analysis Platform — AWS Cloud Deployment
# MSc Cloud Computing, University of Lincoln
# Compliant: UK GDPR · NHS DSP Toolkit · EU AI Act (Research Exemption)
###############################################################################

terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.13"
    }
  }

  # Remote state — S3 + DynamoDB for locking (required for team/CI use)
  backend "s3" {
    bucket         = "hri-platform-tfstate"
    key            = "prod/terraform.tfstate"
    region         = "eu-west-2"          # London — data residency compliance
    encrypt        = true
    dynamodb_table = "hri-platform-tf-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "HRI-Behaviour-Platform"
      Environment = var.environment
      Compliance  = "NHS-DSP-UK-GDPR"
      ManagedBy   = "Terraform"
      Owner       = "Agaba-Solomon-Amogo"
      University  = "University-of-Lincoln"
    }
  }
}

###############################################################################
# VPC — isolated network with private subnets for data residency
###############################################################################
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.8"

  name = "${var.project_name}-vpc"
  cidr = var.vpc_cidr

  azs             = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]
  private_subnets = var.private_subnet_cidrs
  public_subnets  = var.public_subnet_cidrs

  enable_nat_gateway     = true
  single_nat_gateway     = var.environment != "prod"
  enable_dns_hostnames   = true
  enable_dns_support     = true

  # Flow logs → CloudWatch for NHS DSP audit trail
  enable_flow_log                      = true
  create_flow_log_cloudwatch_log_group = true
  create_flow_log_cloudwatch_iam_role  = true
  flow_log_cloudwatch_log_group_retention_in_days = 90

  private_subnet_tags = {
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
    "kubernetes.io/role/internal-elb"           = "1"
  }
  public_subnet_tags = {
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
    "kubernetes.io/role/elb"                    = "1"
  }
}

###############################################################################
# EKS Cluster — Kubernetes for container orchestration
###############################################################################
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.11"

  cluster_name    = var.cluster_name
  cluster_version = "1.30"

  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.private_subnet_ids
  control_plane_subnet_ids = module.vpc.private_subnet_ids

  # Private API endpoint — no public exposure
  cluster_endpoint_private_access = true
  cluster_endpoint_public_access  = var.environment != "prod"

  # Cluster encryption — KMS
  cluster_encryption_config = {
    provider_key_arn = aws_kms_key.eks.arn
    resources        = ["secrets"]
  }

  # EKS Managed Node Groups
  eks_managed_node_groups = {
    # CPU nodes for FastAPI backend
    backend = {
      name           = "backend-ng"
      instance_types = ["t3.medium"]
      min_size       = 2
      max_size       = 6
      desired_size   = 2
      disk_size      = 50

      labels = { role = "backend" }
    }

    # Memory-optimised for Ollama VLM inference
    vlm = {
      name           = "vlm-ng"
      instance_types = ["g4dn.xlarge"]   # GPU for LLaVA inference
      min_size       = 0
      max_size       = 3
      desired_size   = 1
      disk_size      = 100

      labels = { role = "vlm" }
      taints = [{
        key    = "nvidia.com/gpu"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]
    }
  }

  # Enable IRSA for fine-grained pod IAM
  enable_irsa = true

  # CloudWatch logging
  cluster_enabled_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
}

###############################################################################
# KMS — encryption at rest
###############################################################################
resource "aws_kms_key" "eks" {
  description             = "EKS cluster encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_key" "s3" {
  description             = "S3 video storage encryption — NHS DSP compliant"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_key" "rds" {
  description             = "RDS database encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

###############################################################################
# S3 — encrypted video storage with lifecycle policies
###############################################################################
module "video_storage" {
  source  = "terraform-aws-modules/s3-bucket/aws"
  version = "~> 4.1"

  bucket = "${var.project_name}-videos-${var.environment}-${random_id.suffix.hex}"

  # Block all public access — data residency
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true

  # SSE with KMS
  server_side_encryption_configuration = {
    rule = {
      apply_server_side_encryption_by_default = {
        kms_master_key_id = aws_kms_key.s3.arn
        sse_algorithm     = "aws:kms"
      }
    }
  }

  versioning = { enabled = true }

  # Lifecycle: auto-delete processed videos after 90 days (GDPR data minimisation)
  lifecycle_rule = [
    {
      id      = "gdpr-data-minimisation"
      enabled = true
      expiration = { days = 90 }
      noncurrent_version_expiration = { days = 30 }
    }
  ]

  # Access logging for NHS DSP audit trail
  logging = {
    target_bucket = module.access_logs_bucket.s3_bucket_id
    target_prefix = "video-access-logs/"
  }
}

module "access_logs_bucket" {
  source  = "terraform-aws-modules/s3-bucket/aws"
  version = "~> 4.1"
  bucket  = "${var.project_name}-access-logs-${var.environment}-${random_id.suffix.hex}"
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "random_id" "suffix" { byte_length = 4 }

###############################################################################
# RDS PostgreSQL — production database (replaces SQLite)
###############################################################################
module "db" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.6"

  identifier        = "${var.project_name}-db-${var.environment}"
  engine            = "postgres"
  engine_version    = "16"
  instance_class    = var.environment == "prod" ? "db.t3.medium" : "db.t3.micro"
  allocated_storage = 50
  storage_encrypted = true
  kms_key_id        = aws_kms_key.rds.arn

  db_name  = "hri_platform"
  username = "hri_admin"
  manage_master_user_password = true  # Secrets Manager

  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = module.vpc.database_subnet_group_name

  backup_retention_period    = 30   # NHS DSP: 30-day backups
  backup_window              = "03:00-04:00"
  maintenance_window         = "Mon:04:00-Mon:05:00"
  deletion_protection        = var.environment == "prod"
  multi_az                   = var.environment == "prod"
  skip_final_snapshot        = var.environment != "prod"
  final_snapshot_identifier  = "${var.project_name}-final-snapshot"

  # CloudWatch enhanced monitoring
  monitoring_interval    = 60
  create_monitoring_role = true

  parameters = [
    { name = "log_connections",     value = "1" },
    { name = "log_disconnections",  value = "1" },
    { name = "log_duration",        value = "1" },
  ]
}

###############################################################################
# Security Groups
###############################################################################
resource "aws_security_group" "rds" {
  name_prefix = "${var.project_name}-rds-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
    description     = "EKS worker nodes → RDS"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

###############################################################################
# Application Load Balancer + WAF (OWASP protection)
###############################################################################
resource "aws_wafv2_web_acl" "main" {
  name  = "${var.project_name}-waf"
  scope = "REGIONAL"

  default_action { allow {} }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "CommonRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.project_name}-waf"
    sampled_requests_enabled   = true
  }
}

###############################################################################
# CloudWatch — monitoring, alerting, audit trails
###############################################################################
resource "aws_cloudwatch_log_group" "app" {
  name              = "/hri-platform/${var.environment}/app"
  retention_in_days = 90   # NHS DSP: 90-day log retention
  kms_key_id        = aws_kms_key.eks.arn
}

resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  alarm_name          = "${var.project_name}-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 120
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "CPU > 80% for 4 minutes"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_sns_topic" "alerts" {
  name              = "${var.project_name}-alerts"
  kms_master_key_id = "alias/aws/sns"
}

###############################################################################
# Outputs
###############################################################################
output "cluster_endpoint"      { value = module.eks.cluster_endpoint }
output "cluster_name"          { value = module.eks.cluster_name }
output "rds_endpoint"          { value = module.db.db_instance_endpoint }
output "video_bucket_name"     { value = module.video_storage.s3_bucket_id }
output "video_bucket_arn"      { value = module.video_storage.s3_bucket_arn }
output "vpc_id"                { value = module.vpc.vpc_id }
