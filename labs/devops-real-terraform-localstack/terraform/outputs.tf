output "bucket_arn" {
  value = aws_s3_bucket.demo.arn
}

output "role_arn" {
  value = aws_iam_role.lambda_exec.arn
}

output "function_arn" {
  value = aws_lambda_function.demo.arn
}
