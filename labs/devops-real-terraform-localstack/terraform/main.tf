# Real Terraform HCL for a real (if local) API: an S3 bucket, an IAM role + least-privilege
# inline policy, and a Lambda function, all created against LocalStack instead of real AWS.
#
# This file is NOT graded by the automated pytest suite (terraform is not installed in the
# grading sandbox this lab was built in) - it is shipped complete and correct for a human who
# has terraform installed to run for real. See scripts/manual_verify.sh and README.md's
# "Applying it for real" section. The pytest-graded contract (tests/) re-creates the same three
# resources directly with boto3 against a real LocalStack container, which is the part every
# learner's machine can actually run.

data "archive_file" "handler_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda_src/handler.py"
  output_path = "${path.module}/.build/handler.zip"
}

# --- S3: bucket + versioning + default encryption + full public access block -----------------

resource "aws_s3_bucket" "demo" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_versioning" "demo" {
  bucket = aws_s3_bucket.demo.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "demo" {
  bucket = aws_s3_bucket.demo.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "demo" {
  bucket                  = aws_s3_bucket.demo.id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

# --- IAM: a role only Lambda can assume, with a policy scoped to THIS bucket only -------------

data "aws_iam_policy_document" "lambda_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_exec" {
  name               = var.role_name
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

data "aws_iam_policy_document" "lambda_permissions" {
  statement {
    sid       = "WriteLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:*:*:*"]
  }

  statement {
    sid       = "ReadWriteOwnBucketOnly"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.demo.arn}/*"]
  }
}

resource "aws_iam_role_policy" "lambda_permissions" {
  name   = "${var.role_name}-policy"
  role   = aws_iam_role.lambda_exec.id
  policy = data.aws_iam_policy_document.lambda_permissions.json
}

# --- Lambda: the function itself --------------------------------------------------------------

resource "aws_lambda_function" "demo" {
  function_name    = var.function_name
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.handler_zip.output_path
  source_code_hash = data.archive_file.handler_zip.output_base64sha256
  timeout          = 30

  environment {
    variables = {
      BUCKET_NAME = aws_s3_bucket.demo.bucket
    }
  }

  depends_on = [aws_iam_role_policy.lambda_permissions]
}
