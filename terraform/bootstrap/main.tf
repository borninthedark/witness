# ================================================================
# HCP Terraform OIDC Bootstrap
# ================================================================
# Creates IAM OIDC provider + role so HCP Terraform workspaces
# can authenticate to AWS via dynamic provider credentials
# (short-lived STS tokens) instead of static access keys.
#
# Run once locally:
#   cd terraform/bootstrap
#   terraform init && terraform apply
# ================================================================

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

# ================================================================
# OIDC Identity Provider for HCP Terraform
# ================================================================

resource "aws_iam_openid_connect_provider" "tfc" {
  url = "https://app.terraform.io"

  client_id_list  = ["aws.workload.identity"]
  thumbprint_list = ["9e99a48a9960b14926bb7f3b02e22da2b0ab7280"]
}

# ================================================================
# IAM Role trusted by HCP Terraform workspaces
# ================================================================

resource "aws_iam_role" "tfc" {
  name = "${var.project}-tfc-oidc"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "sts:AssumeRoleWithWebIdentity"
        Principal = {
          Federated = aws_iam_openid_connect_provider.tfc.arn
        }
        Condition = {
          StringEquals = {
            "app.terraform.io:aud" = "aws.workload.identity"
          }
          StringLike = {
            "app.terraform.io:sub" = [
              for ws in var.tfc_workspace_names :
              "organization:${var.tfc_organization}:project:*:workspace:${ws}:run_phase:*"
            ]
          }
        }
      }
    ]
  })
}

# ================================================================
# IAM Policy — permissions for managed infrastructure
# ================================================================
# Covers all services used by dev/prod workspaces:
#   security (KMS, CloudTrail, Config), networking (VPC),
#   app-runner (ECR, Secrets Manager, App Runner),
#   observability (CloudWatch), codepipeline (CodePipeline,
#   CodeBuild, CodeStar Connections, S3 artifacts)
# ================================================================

resource "aws_iam_policy" "tfc" {
  name        = "${var.project}-tfc-oidc"
  description = "Permissions for HCP Terraform OIDC workspaces to manage ${var.project} infrastructure"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # ----------------------------------------------------------
      # EC2 / VPC
      # ----------------------------------------------------------
      {
        Sid    = "VPC"
        Effect = "Allow"
        Action = [
          "ec2:Describe*",
          "ec2:CreateVpc",
          "ec2:DeleteVpc",
          "ec2:ModifyVpcAttribute",
          "ec2:CreateSubnet",
          "ec2:DeleteSubnet",
          "ec2:CreateRouteTable",
          "ec2:DeleteRouteTable",
          "ec2:AssociateRouteTable",
          "ec2:DisassociateRouteTable",
          "ec2:CreateRoute",
          "ec2:DeleteRoute",
          "ec2:CreateInternetGateway",
          "ec2:DeleteInternetGateway",
          "ec2:AttachInternetGateway",
          "ec2:DetachInternetGateway",
          "ec2:CreateNatGateway",
          "ec2:DeleteNatGateway",
          "ec2:AllocateAddress",
          "ec2:ReleaseAddress",
          "ec2:AssociateAddress",
          "ec2:DisassociateAddress",
          "ec2:CreateTags",
          "ec2:DeleteTags",
          "ec2:CreateSecurityGroup",
          "ec2:DeleteSecurityGroup",
          "ec2:AuthorizeSecurityGroupIngress",
          "ec2:AuthorizeSecurityGroupEgress",
          "ec2:RevokeSecurityGroupIngress",
          "ec2:RevokeSecurityGroupEgress",
          "ec2:CreateFlowLogs",
          "ec2:DeleteFlowLogs",
          "ec2:CreateNetworkAclEntry",
          "ec2:DeleteNetworkAclEntry",
          "ec2:CreateNetworkAcl",
          "ec2:DeleteNetworkAcl",
          "ec2:ReplaceNetworkAclAssociation",
          "ec2:ReplaceNetworkAclEntry",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # App Runner
      # ----------------------------------------------------------
      {
        Sid    = "AppRunner"
        Effect = "Allow"
        Action = [
          "apprunner:Create*",
          "apprunner:Delete*",
          "apprunner:Describe*",
          "apprunner:List*",
          "apprunner:Update*",
          "apprunner:TagResource",
          "apprunner:UntagResource",
          "apprunner:AssociateCustomDomain",
          "apprunner:DisassociateCustomDomain",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # ECR
      # ----------------------------------------------------------
      {
        Sid    = "ECR"
        Effect = "Allow"
        Action = [
          "ecr:CreateRepository",
          "ecr:DeleteRepository",
          "ecr:Describe*",
          "ecr:Get*",
          "ecr:List*",
          "ecr:SetRepositoryPolicy",
          "ecr:DeleteRepositoryPolicy",
          "ecr:PutLifecyclePolicy",
          "ecr:DeleteLifecyclePolicy",
          "ecr:GetLifecyclePolicy",
          "ecr:GetLifecyclePolicyPreview",
          "ecr:TagResource",
          "ecr:UntagResource",
          "ecr:PutImageScanningConfiguration",
          "ecr:PutImageTagMutability",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # KMS
      # ----------------------------------------------------------
      {
        Sid    = "KMS"
        Effect = "Allow"
        Action = [
          "kms:CreateAlias",
          "kms:CreateKey",
          "kms:CreateGrant",
          "kms:DeleteAlias",
          "kms:Decrypt",
          "kms:Describe*",
          "kms:EnableKeyRotation",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:Get*",
          "kms:List*",
          "kms:PutKeyPolicy",
          "kms:ReEncrypt*",
          "kms:ScheduleKeyDeletion",
          "kms:TagResource",
          "kms:UntagResource",
          "kms:UpdateAlias",
          "kms:UpdateKeyDescription",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # Secrets Manager
      # ----------------------------------------------------------
      {
        Sid    = "SecretsManager"
        Effect = "Allow"
        Action = [
          "secretsmanager:CreateSecret",
          "secretsmanager:DeleteSecret",
          "secretsmanager:Describe*",
          "secretsmanager:Get*",
          "secretsmanager:List*",
          "secretsmanager:PutSecretValue",
          "secretsmanager:UpdateSecret",
          "secretsmanager:TagResource",
          "secretsmanager:UntagResource",
          "secretsmanager:RestoreSecret",
          "secretsmanager:PutResourcePolicy",
          "secretsmanager:DeleteResourcePolicy",
          "secretsmanager:GetResourcePolicy",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # CloudWatch Logs + Metrics + Dashboards + Alarms
      # ----------------------------------------------------------
      {
        Sid    = "CloudWatch"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:DeleteLogGroup",
          "logs:Describe*",
          "logs:List*",
          "logs:PutRetentionPolicy",
          "logs:DeleteRetentionPolicy",
          "logs:TagResource",
          "logs:UntagResource",
          "logs:TagLogGroup",
          "logs:UntagLogGroup",
          "logs:AssociateKmsKey",
          "logs:DisassociateKmsKey",
          "logs:PutLogEvents",
          "logs:CreateLogStream",
          "cloudwatch:PutMetricAlarm",
          "cloudwatch:DeleteAlarms",
          "cloudwatch:Describe*",
          "cloudwatch:Get*",
          "cloudwatch:List*",
          "cloudwatch:TagResource",
          "cloudwatch:UntagResource",
          "cloudwatch:PutDashboard",
          "cloudwatch:DeleteDashboards",
          "cloudwatch:GetDashboard",
          "cloudwatch:ListDashboards",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # CloudTrail
      # ----------------------------------------------------------
      {
        Sid    = "CloudTrail"
        Effect = "Allow"
        Action = [
          "cloudtrail:CreateTrail",
          "cloudtrail:DeleteTrail",
          "cloudtrail:Describe*",
          "cloudtrail:Get*",
          "cloudtrail:List*",
          "cloudtrail:PutEventSelectors",
          "cloudtrail:StartLogging",
          "cloudtrail:StopLogging",
          "cloudtrail:UpdateTrail",
          "cloudtrail:AddTags",
          "cloudtrail:RemoveTags",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # S3 (CloudTrail bucket, pipeline artifacts)
      # ----------------------------------------------------------
      {
        Sid    = "S3"
        Effect = "Allow"
        Action = [
          "s3:CreateBucket",
          "s3:DeleteBucket",
          "s3:Get*",
          "s3:List*",
          "s3:PutBucketPolicy",
          "s3:DeleteBucketPolicy",
          "s3:PutBucketVersioning",
          "s3:PutBucketTagging",
          "s3:PutBucketPublicAccessBlock",
          "s3:GetBucketPublicAccessBlock",
          "s3:PutEncryptionConfiguration",
          "s3:PutLifecycleConfiguration",
          "s3:PutBucketLogging",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:PutObjectAcl",
          "s3:PutBucketAcl",
          "s3:PutBucketOwnershipControls",
          "s3:GetBucketOwnershipControls",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # AWS Config
      # ----------------------------------------------------------
      {
        Sid    = "Config"
        Effect = "Allow"
        Action = [
          "config:Describe*",
          "config:Get*",
          "config:List*",
          "config:Put*",
          "config:DeleteConfigurationRecorder",
          "config:DeleteDeliveryChannel",
          "config:StartConfigurationRecorder",
          "config:StopConfigurationRecorder",
          "config:TagResource",
          "config:UntagResource",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # CodePipeline
      # ----------------------------------------------------------
      {
        Sid    = "CodePipeline"
        Effect = "Allow"
        Action = [
          "codepipeline:CreatePipeline",
          "codepipeline:DeletePipeline",
          "codepipeline:GetPipeline",
          "codepipeline:GetPipelineState",
          "codepipeline:ListPipelines",
          "codepipeline:UpdatePipeline",
          "codepipeline:TagResource",
          "codepipeline:UntagResource",
          "codepipeline:ListTagsForResource",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # CodeBuild
      # ----------------------------------------------------------
      {
        Sid    = "CodeBuild"
        Effect = "Allow"
        Action = [
          "codebuild:CreateProject",
          "codebuild:DeleteProject",
          "codebuild:UpdateProject",
          "codebuild:BatchGetProjects",
          "codebuild:ListProjects",
          "codebuild:CreateWebhook",
          "codebuild:DeleteWebhook",
          "codebuild:UpdateWebhook",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # CodeStar Connections
      # ----------------------------------------------------------
      {
        Sid    = "CodeStarConnections"
        Effect = "Allow"
        Action = [
          "codestar-connections:CreateConnection",
          "codestar-connections:DeleteConnection",
          "codestar-connections:GetConnection",
          "codestar-connections:ListConnections",
          "codestar-connections:ListTagsForResource",
          "codestar-connections:TagResource",
          "codestar-connections:UntagResource",
          "codestar-connections:PassConnection",
          "codestar-connections:UseConnection",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # IAM (enumerated, no iam:*)
      # ----------------------------------------------------------
      {
        Sid    = "IAM"
        Effect = "Allow"
        Action = [
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:GetRole",
          "iam:ListRolePolicies",
          "iam:ListAttachedRolePolicies",
          "iam:ListInstanceProfilesForRole",
          "iam:UpdateAssumeRolePolicy",
          "iam:PassRole",
          "iam:TagRole",
          "iam:UntagRole",
          "iam:CreatePolicy",
          "iam:DeletePolicy",
          "iam:GetPolicy",
          "iam:GetPolicyVersion",
          "iam:ListPolicyVersions",
          "iam:CreatePolicyVersion",
          "iam:DeletePolicyVersion",
          "iam:TagPolicy",
          "iam:UntagPolicy",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:GetRolePolicy",
          "iam:CreateServiceLinkedRole",
          "iam:DeleteServiceLinkedRole",
          "iam:GetServiceLinkedRoleDeletionStatus",
          "iam:ListRoleTags",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # STS (caller identity checks)
      # ----------------------------------------------------------
      {
        Sid      = "STS"
        Effect   = "Allow"
        Action   = ["sts:GetCallerIdentity"]
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "tfc" {
  role       = aws_iam_role.tfc.name
  policy_arn = aws_iam_policy.tfc.arn
}
