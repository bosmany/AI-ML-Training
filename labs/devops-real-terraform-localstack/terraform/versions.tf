terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

# Every endpoint points at the same LocalStack edge port (single port since LocalStack v2).
# The four "skip_*" flags and s3_use_path_style are what make the real AWS provider talk to a
# local fake instead of needing real credentials or a real DNS-resolvable bucket vhost.
provider "aws" {
  region     = var.region
  access_key = "test"
  secret_key = "test"

  s3_use_path_style           = true
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    s3     = var.localstack_endpoint
    iam    = var.localstack_endpoint
    lambda = var.localstack_endpoint
    sts    = var.localstack_endpoint
    logs   = var.localstack_endpoint
  }
}
