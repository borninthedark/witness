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
# IAM Policies — permissions for managed infrastructure
# ================================================================
# Split into two policies to stay under the 6,144 byte managed
# policy size limit.
#
# Policy 1 (core): VPC, App Runner, ECR, KMS, Secrets Manager,
#   CloudWatch, Route 53, STS
# Policy 2 (governance + CI/CD): CloudTrail, S3, Config,
#   CodePipeline, CodeBuild, CodeStar, IAM
# ================================================================

resource "aws_iam_policy" "tfc_core" {
  name        = "${var.project}-tfc-oidc-core"
  description = "Core infrastructure permissions for HCP Terraform OIDC workspaces"

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
          "apprunner:AssociateWebAcl",
          "apprunner:DisassociateWebAcl",
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
      # Route 53 (DNS records + domain registration)
      # ----------------------------------------------------------
      {
        Sid    = "Route53"
        Effect = "Allow"
        Action = [
          "route53:GetHostedZone",
          "route53:ListHostedZones",
          "route53:ListResourceRecordSets",
          "route53:ChangeResourceRecordSets",
          "route53:GetChange",
          "route53:ListTagsForResource",
          "route53domains:GetDomainDetail",
          "route53domains:ListDomains",
          "route53domains:ListTagsForDomain",
          "route53domains:UpdateDomainContact",
          "route53domains:UpdateDomainNameservers",
          "route53domains:GetOperationDetail",
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

resource "aws_iam_policy" "tfc_governance" {
  name        = "${var.project}-tfc-oidc-governance"
  description = "Governance and CI/CD permissions for HCP Terraform OIDC workspaces"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
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
    ]
  })
}

resource "aws_iam_policy" "tfc_wellarchitected" {
  name        = "${var.project}-tfc-oidc-wellarchitected"
  description = "WAF/LZA security services for HCP Terraform OIDC workspaces"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # ----------------------------------------------------------
      # VPC Endpoints
      # ----------------------------------------------------------
      {
        Sid    = "VPCEndpoints"
        Effect = "Allow"
        Action = [
          "ec2:CreateVpcEndpoint",
          "ec2:DeleteVpcEndpoints",
          "ec2:ModifyVpcEndpoint",
          "ec2:DescribeVpcEndpoints",
          "ec2:DescribeVpcEndpointServices",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # SNS (alarm notifications)
      # ----------------------------------------------------------
      {
        Sid    = "SNS"
        Effect = "Allow"
        Action = [
          "sns:CreateTopic",
          "sns:DeleteTopic",
          "sns:GetTopicAttributes",
          "sns:SetTopicAttributes",
          "sns:ListTopics",
          "sns:Subscribe",
          "sns:Unsubscribe",
          "sns:ListSubscriptionsByTopic",
          "sns:TagResource",
          "sns:UntagResource",
          "sns:ListTagsForResource",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # WAFv2
      # ----------------------------------------------------------
      {
        Sid    = "WAFv2"
        Effect = "Allow"
        Action = [
          "wafv2:CreateWebACL",
          "wafv2:DeleteWebACL",
          "wafv2:GetWebACL",
          "wafv2:ListWebACLs",
          "wafv2:UpdateWebACL",
          "wafv2:AssociateWebACL",
          "wafv2:DisassociateWebACL",
          "wafv2:GetWebACLForResource",
          "wafv2:ListTagsForResource",
          "wafv2:TagResource",
          "wafv2:UntagResource",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # GuardDuty
      # ----------------------------------------------------------
      {
        Sid    = "GuardDuty"
        Effect = "Allow"
        Action = [
          "guardduty:CreateDetector",
          "guardduty:DeleteDetector",
          "guardduty:GetDetector",
          "guardduty:ListDetectors",
          "guardduty:UpdateDetector",
          "guardduty:TagResource",
          "guardduty:UntagResource",
          "guardduty:ListTagsForResource",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # Security Hub
      # ----------------------------------------------------------
      {
        Sid    = "SecurityHub"
        Effect = "Allow"
        Action = [
          "securityhub:EnableSecurityHub",
          "securityhub:DisableSecurityHub",
          "securityhub:DescribeHub",
          "securityhub:GetEnabledStandards",
          "securityhub:BatchEnableStandards",
          "securityhub:BatchDisableStandards",
          "securityhub:DescribeStandards",
          "securityhub:DescribeStandardsControls",
          "securityhub:GetFindings",
          "securityhub:TagResource",
          "securityhub:UntagResource",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # Budgets
      # ----------------------------------------------------------
      {
        Sid    = "Budgets"
        Effect = "Allow"
        Action = [
          "budgets:CreateBudgetAction",
          "budgets:DeleteBudgetAction",
          "budgets:DescribeBudget",
          "budgets:ModifyBudget",
          "budgets:ViewBudget",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # X-Ray (App Runner observability)
      # ----------------------------------------------------------
      {
        Sid    = "XRay"
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
          "xray:GetSamplingRules",
          "xray:GetSamplingTargets",
        ]
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "tfc_core" {
  role       = aws_iam_role.tfc.name
  policy_arn = aws_iam_policy.tfc_core.arn
}

resource "aws_iam_role_policy_attachment" "tfc_governance" {
  role       = aws_iam_role.tfc.name
  policy_arn = aws_iam_policy.tfc_governance.arn
}

resource "aws_iam_role_policy_attachment" "tfc_wellarchitected" {
  role       = aws_iam_role.tfc.name
  policy_arn = aws_iam_policy.tfc_wellarchitected.arn
}

# ================================================================
# GitHub Actions OIDC — ECR image push from CI/CD
# ================================================================

resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["ffffffffffffffffffffffffffffffffffffffff"]
}

resource "aws_iam_role" "github_actions" {
  name = "${var.project}-github-actions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "sts:AssumeRoleWithWebIdentity"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github.arn
        }
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_repository}:*"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "github_ecr_push" {
  name = "ecr-push"
  role = aws_iam_role.github_actions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ECRAuth"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "ECRPush"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
        ]
        Resource = "arn:aws:ecr:${var.aws_region}:*:repository/${var.project}-*"
      },
    ]
  })
}

# ================================================================
# Route 53 Domain Registration
# ================================================================
# Registers the domain via Route 53 Domains and automatically
# creates a public hosted zone. No external registrar needed.
# Both dev and prod workspaces look up the zone via data source.
# ================================================================

resource "aws_route53domains_domain" "main" {
  domain_name = var.domain_name
  auto_renew  = true

  admin_contact {
    first_name     = var.contact_first_name
    last_name      = var.contact_last_name
    email          = var.contact_email
    phone_number   = var.contact_phone
    contact_type   = "PERSON"
    address_line_1 = var.contact_address_line_1
    city           = var.contact_city
    state          = var.contact_state
    zip_code       = var.contact_zip_code
    country_code   = var.contact_country_code
  }

  registrant_contact {
    first_name     = var.contact_first_name
    last_name      = var.contact_last_name
    email          = var.contact_email
    phone_number   = var.contact_phone
    contact_type   = "PERSON"
    address_line_1 = var.contact_address_line_1
    city           = var.contact_city
    state          = var.contact_state
    zip_code       = var.contact_zip_code
    country_code   = var.contact_country_code
  }

  tech_contact {
    first_name     = var.contact_first_name
    last_name      = var.contact_last_name
    email          = var.contact_email
    phone_number   = var.contact_phone
    contact_type   = "PERSON"
    address_line_1 = var.contact_address_line_1
    city           = var.contact_city
    state          = var.contact_state
    zip_code       = var.contact_zip_code
    country_code   = var.contact_country_code
  }
}
