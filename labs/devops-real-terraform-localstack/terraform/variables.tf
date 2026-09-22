variable "region" {
  description = "AWS region (LocalStack accepts any well-formed region; us-east-1 is the default)."
  type        = string
  default     = "us-east-1"
}

variable "localstack_endpoint" {
  description = "LocalStack edge endpoint. Override with -var if you mapped a different host port."
  type        = string
  default     = "http://localhost:4566"
}

variable "bucket_name" {
  description = "Name of the S3 bucket the demo stack creates."
  type        = string
  default     = "tf-localstack-demo-bucket"
}

variable "role_name" {
  description = "Name of the IAM role the Lambda function assumes."
  type        = string
  default     = "tf-localstack-demo-role"
}

variable "function_name" {
  description = "Name of the Lambda function."
  type        = string
  default     = "tf-localstack-demo-fn"
}
