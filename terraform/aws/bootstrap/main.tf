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
  #checkov:skip=CKV_AWS_355:Terraform provisioning role — EC2/VPC and KMS resources use AWS-assigned IDs that cannot be predicted at policy creation time; constrained by OIDC workspace trust
  #checkov:skip=CKV_AWS_290:Terraform provisioning role — VPC/KMS infrastructure creation requires write access to AWS-assigned resources; constrained by OIDC workspace trust
  #checkov:skip=CKV_AWS_289:Terraform provisioning role — KMS key policy management requires * resource (AWS-assigned key IDs); constrained by OIDC workspace trust
  name        = "${var.project}-tfc-oidc-core"
  description = "Core infrastructure permissions for HCP Terraform OIDC workspaces"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # ----------------------------------------------------------
      # EC2 / VPC — AWS-assigned IDs, cannot be resource-scoped
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
        Sid    = "AppRunnerRead"
        Effect = "Allow"
        Action = [
          "apprunner:Describe*",
          "apprunner:List*",
        ]
        Resource = "*"
      },
      {
        Sid    = "AppRunnerWrite"
        Effect = "Allow"
        Action = [
          "apprunner:Create*",
          "apprunner:Delete*",
          "apprunner:Update*",
          "apprunner:TagResource",
          "apprunner:UntagResource",
          "apprunner:AssociateCustomDomain",
          "apprunner:DisassociateCustomDomain",
          "apprunner:AssociateWebAcl",
          "apprunner:DisassociateWebAcl",
        ]
        Resource = "arn:aws:apprunner:${var.aws_region}:*:*"
      },

      # ----------------------------------------------------------
      # ECR (scoped to project-prefixed repositories)
      # ----------------------------------------------------------
      {
        Sid    = "ECRRead"
        Effect = "Allow"
        Action = [
          "ecr:Describe*",
          "ecr:Get*",
          "ecr:List*",
        ]
        Resource = "*"
      },
      {
        Sid    = "ECRWrite"
        Effect = "Allow"
        Action = [
          "ecr:CreateRepository",
          "ecr:DeleteRepository",
          "ecr:SetRepositoryPolicy",
          "ecr:DeleteRepositoryPolicy",
          "ecr:PutLifecyclePolicy",
          "ecr:DeleteLifecyclePolicy",
          "ecr:TagResource",
          "ecr:UntagResource",
          "ecr:PutImageScanningConfiguration",
          "ecr:PutImageTagMutability",
        ]
        Resource = "arn:aws:ecr:${var.aws_region}:*:repository/${var.project}-*"
      },

      # ----------------------------------------------------------
      # KMS — management (AWS-assigned key IDs, cannot scope)
      # ----------------------------------------------------------
      {
        Sid    = "KMSManagement"
        Effect = "Allow"
        Action = [
          "kms:CreateAlias",
          "kms:CreateKey",
          "kms:CreateGrant",
          "kms:DeleteAlias",
          "kms:Describe*",
          "kms:EnableKeyRotation",
          "kms:Get*",
          "kms:List*",
          "kms:PutKeyPolicy",
          "kms:ScheduleKeyDeletion",
          "kms:TagResource",
          "kms:UntagResource",
          "kms:UpdateAlias",
          "kms:UpdateKeyDescription",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # KMS — data-plane encryption (ViaService scoped)
      # ----------------------------------------------------------
      {
        Sid    = "KMSEncryption"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:ReEncrypt*",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = [
              "secretsmanager.${var.aws_region}.amazonaws.com",
              "s3.${var.aws_region}.amazonaws.com",
              "logs.${var.aws_region}.amazonaws.com",
              "dynamodb.${var.aws_region}.amazonaws.com",
            ]
          }
        }
      },

      # ----------------------------------------------------------
      # Secrets Manager (scoped to project-prefixed secrets)
      # ----------------------------------------------------------
      {
        Sid      = "SecretsManagerList"
        Effect   = "Allow"
        Action   = ["secretsmanager:ListSecrets"]
        Resource = "*"
      },
      {
        Sid    = "SecretsManagerRead"
        Effect = "Allow"
        Action = [
          "secretsmanager:DescribeSecret",
          "secretsmanager:GetSecretValue",
          "secretsmanager:GetResourcePolicy",
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:*:secret:${var.project}-*"
      },
      {
        Sid    = "SecretsManagerWrite"
        Effect = "Allow"
        Action = [
          "secretsmanager:CreateSecret",
          "secretsmanager:DeleteSecret",
          "secretsmanager:PutSecretValue",
          "secretsmanager:UpdateSecret",
          "secretsmanager:TagResource",
          "secretsmanager:UntagResource",
          "secretsmanager:RestoreSecret",
          "secretsmanager:PutResourcePolicy",
          "secretsmanager:DeleteResourcePolicy",
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:*:secret:${var.project}-*"
      },

      # ----------------------------------------------------------
      # CloudWatch Logs + Metrics + Dashboards + Alarms
      # Log group names vary (/aws/apprunner/*, /aws/lambda/*)
      # so cannot be project-scoped.
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
      # Route 53 — AWS-assigned zone IDs, cannot be scoped
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
  #checkov:skip=CKV_AWS_355:Terraform provisioning role — Config recorder and CodeStar connections use AWS-assigned IDs; constrained by OIDC workspace trust
  #checkov:skip=CKV_AWS_290:Terraform provisioning role — Config and CodeStar write ops require * for AWS-singleton resources; constrained by OIDC workspace trust
  name        = "${var.project}-tfc-oidc-governance"
  description = "Governance and CI/CD permissions for HCP Terraform OIDC workspaces"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # ----------------------------------------------------------
      # CloudTrail (scoped to project-prefixed trails)
      # ----------------------------------------------------------
      {
        Sid    = "CloudTrailRead"
        Effect = "Allow"
        Action = [
          "cloudtrail:Describe*",
          "cloudtrail:Get*",
          "cloudtrail:List*",
        ]
        Resource = "*"
      },
      {
        Sid    = "CloudTrailWrite"
        Effect = "Allow"
        Action = [
          "cloudtrail:CreateTrail",
          "cloudtrail:DeleteTrail",
          "cloudtrail:PutEventSelectors",
          "cloudtrail:StartLogging",
          "cloudtrail:StopLogging",
          "cloudtrail:UpdateTrail",
          "cloudtrail:AddTags",
          "cloudtrail:RemoveTags",
        ]
        Resource = "arn:aws:cloudtrail:${var.aws_region}:*:trail/${var.project}-*"
      },

      # ----------------------------------------------------------
      # S3 (scoped to project-prefixed buckets)
      # ----------------------------------------------------------
      {
        Sid    = "S3Buckets"
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
          "s3:PutBucketCors",
          "s3:GetBucketCors",
        ]
        Resource = [
          "arn:aws:s3:::${var.project}-*",
          "arn:aws:s3:::${var.project}-*/*",
        ]
      },

      # ----------------------------------------------------------
      # AWS Config — singleton recorder/channel, cannot scope
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
      # CodePipeline (scoped to project-prefixed pipelines)
      # ----------------------------------------------------------
      {
        Sid    = "CodePipelineRead"
        Effect = "Allow"
        Action = [
          "codepipeline:GetPipeline",
          "codepipeline:GetPipelineState",
          "codepipeline:ListPipelines",
          "codepipeline:ListTagsForResource",
        ]
        Resource = "*"
      },
      {
        Sid    = "CodePipelineWrite"
        Effect = "Allow"
        Action = [
          "codepipeline:CreatePipeline",
          "codepipeline:DeletePipeline",
          "codepipeline:UpdatePipeline",
          "codepipeline:TagResource",
          "codepipeline:UntagResource",
        ]
        Resource = "arn:aws:codepipeline:${var.aws_region}:*:${var.project}-*"
      },

      # ----------------------------------------------------------
      # CodeBuild (scoped to project-prefixed projects)
      # ----------------------------------------------------------
      {
        Sid    = "CodeBuildRead"
        Effect = "Allow"
        Action = [
          "codebuild:BatchGetProjects",
          "codebuild:ListProjects",
        ]
        Resource = "*"
      },
      {
        Sid    = "CodeBuildWrite"
        Effect = "Allow"
        Action = [
          "codebuild:CreateProject",
          "codebuild:DeleteProject",
          "codebuild:UpdateProject",
          "codebuild:CreateWebhook",
          "codebuild:DeleteWebhook",
          "codebuild:UpdateWebhook",
        ]
        Resource = "arn:aws:codebuild:${var.aws_region}:*:project/${var.project}-*"
      },

      # ----------------------------------------------------------
      # CodeStar Connections — AWS-assigned UUIDs, cannot scope
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
      # IAM (scoped to project-prefixed roles/policies + SLRs)
      # ----------------------------------------------------------
      {
        Sid    = "IAMRead"
        Effect = "Allow"
        Action = [
          "iam:GetRole",
          "iam:GetPolicy",
          "iam:GetPolicyVersion",
          "iam:GetRolePolicy",
          "iam:ListRolePolicies",
          "iam:ListAttachedRolePolicies",
          "iam:ListInstanceProfilesForRole",
          "iam:ListPolicyVersions",
          "iam:ListRoleTags",
          "iam:GetServiceLinkedRoleDeletionStatus",
        ]
        Resource = "*"
      },
      {
        Sid    = "IAMWrite"
        Effect = "Allow"
        Action = [
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:UpdateAssumeRolePolicy",
          "iam:PassRole",
          "iam:TagRole",
          "iam:UntagRole",
          "iam:CreatePolicy",
          "iam:DeletePolicy",
          "iam:CreatePolicyVersion",
          "iam:DeletePolicyVersion",
          "iam:TagPolicy",
          "iam:UntagPolicy",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
        ]
        Resource = [
          "arn:aws:iam::*:role/${var.project}-*",
          "arn:aws:iam::*:policy/${var.project}-*",
        ]
      },
      {
        Sid    = "IAMServiceLinkedRoles"
        Effect = "Allow"
        Action = [
          "iam:CreateServiceLinkedRole",
          "iam:DeleteServiceLinkedRole",
        ]
        Resource = "arn:aws:iam::*:role/aws-service-role/*"
      },
    ]
  })
}

resource "aws_iam_policy" "tfc_wellarchitected" {
  #checkov:skip=CKV_AWS_355:Terraform provisioning role — VPC endpoints, WAF, GuardDuty, SecurityHub, CloudFront, and ACM use AWS-assigned IDs; constrained by OIDC workspace trust
  #checkov:skip=CKV_AWS_290:Terraform provisioning role — security services require write access to AWS-assigned resources for initial provisioning; constrained by OIDC workspace trust
  #checkov:skip=CKV_AWS_289:Terraform provisioning role — SNS/WAF resource association required for alarm routing and WAF attachment; constrained by OIDC workspace trust
  name        = "${var.project}-tfc-oidc-wellarchitected"
  description = "WAF/LZA security services for HCP Terraform OIDC workspaces"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # ----------------------------------------------------------
      # VPC Endpoints — AWS-assigned IDs, cannot scope
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
      # SNS (scoped to project-prefixed topics)
      # ----------------------------------------------------------
      {
        Sid    = "SNSRead"
        Effect = "Allow"
        Action = [
          "sns:GetTopicAttributes",
          "sns:ListTopics",
          "sns:ListSubscriptionsByTopic",
          "sns:ListTagsForResource",
        ]
        Resource = "*"
      },
      {
        Sid    = "SNSWrite"
        Effect = "Allow"
        Action = [
          "sns:CreateTopic",
          "sns:DeleteTopic",
          "sns:SetTopicAttributes",
          "sns:Subscribe",
          "sns:Unsubscribe",
          "sns:TagResource",
          "sns:UntagResource",
        ]
        Resource = "arn:aws:sns:${var.aws_region}:*:${var.project}-*"
      },

      # ----------------------------------------------------------
      # WAFv2 — AWS-assigned ACL IDs, cannot scope
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
      # GuardDuty — AWS-assigned detector IDs, cannot scope
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
      # Security Hub — account-level service, cannot scope
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
      # Budgets — account-level service, cannot scope
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

      # ----------------------------------------------------------
      # CloudFront — AWS-assigned distribution IDs, cannot scope
      # ----------------------------------------------------------
      {
        Sid    = "CloudFront"
        Effect = "Allow"
        Action = [
          "cloudfront:CreateDistribution",
          "cloudfront:DeleteDistribution",
          "cloudfront:GetDistribution",
          "cloudfront:UpdateDistribution",
          "cloudfront:CreateOriginAccessControl",
          "cloudfront:DeleteOriginAccessControl",
          "cloudfront:GetOriginAccessControl",
          "cloudfront:UpdateOriginAccessControl",
          "cloudfront:ListDistributions",
          "cloudfront:ListOriginAccessControls",
          "cloudfront:GetCachePolicy",
          "cloudfront:ListCachePolicies",
          "cloudfront:GetResponseHeadersPolicy",
          "cloudfront:ListResponseHeadersPolicies",
          "cloudfront:TagResource",
          "cloudfront:UntagResource",
          "cloudfront:ListTagsForResource",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # ACM — AWS-assigned certificate ARNs, cannot scope
      # ----------------------------------------------------------
      {
        Sid    = "ACM"
        Effect = "Allow"
        Action = [
          "acm:RequestCertificate",
          "acm:DeleteCertificate",
          "acm:DescribeCertificate",
          "acm:ListCertificates",
          "acm:ListTagsForCertificate",
          "acm:AddTagsToCertificate",
          "acm:RemoveTagsFromCertificate",
          "acm:GetCertificate",
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

resource "aws_iam_policy" "tfc_serverless" {
  #checkov:skip=CKV_AWS_355:Terraform provisioning role — Lambda/DynamoDB/Scheduler read (Get/List) actions require * for plan-phase state reads; write actions scoped to project prefix
  name        = "${var.project}-tfc-oidc-serverless"
  description = "Serverless (Lambda, DynamoDB, EventBridge) permissions for HCP Terraform OIDC"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # ----------------------------------------------------------
      # Lambda — read-only (list/describe/get)
      # ----------------------------------------------------------
      {
        Sid    = "LambdaRead"
        Effect = "Allow"
        Action = [
          "lambda:GetFunction",
          "lambda:GetFunctionConfiguration",
          "lambda:GetLayerVersion",
          "lambda:GetPolicy",
          "lambda:GetEventSourceMapping",
          "lambda:ListFunctions",
          "lambda:ListVersionsByFunction",
          "lambda:ListLayers",
          "lambda:ListTags",
          "lambda:ListEventSourceMappings",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # Lambda — write (scoped to project prefix)
      # ----------------------------------------------------------
      {
        Sid    = "LambdaWrite"
        Effect = "Allow"
        Action = [
          "lambda:CreateFunction",
          "lambda:DeleteFunction",
          "lambda:UpdateFunctionCode",
          "lambda:UpdateFunctionConfiguration",
          "lambda:PublishLayerVersion",
          "lambda:DeleteLayerVersion",
          "lambda:AddPermission",
          "lambda:RemovePermission",
          "lambda:TagResource",
          "lambda:UntagResource",
          "lambda:CreateEventSourceMapping",
          "lambda:DeleteEventSourceMapping",
          "lambda:UpdateEventSourceMapping",
        ]
        Resource = [
          "arn:aws:lambda:${var.aws_region}:*:function:${var.project}-*",
          "arn:aws:lambda:${var.aws_region}:*:layer:${var.project}-*",
          "arn:aws:lambda:${var.aws_region}:*:event-source-mapping:*",
        ]
      },

      # ----------------------------------------------------------
      # DynamoDB — read-only
      # ----------------------------------------------------------
      {
        Sid    = "DynamoDBRead"
        Effect = "Allow"
        Action = [
          "dynamodb:DescribeTable",
          "dynamodb:DescribeContinuousBackups",
          "dynamodb:DescribeTimeToLive",
          "dynamodb:DescribeKinesisStreamingDestination",
          "dynamodb:ListTables",
          "dynamodb:ListTagsOfResource",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # DynamoDB — write (scoped to project prefix)
      # ----------------------------------------------------------
      {
        Sid    = "DynamoDBWrite"
        Effect = "Allow"
        Action = [
          "dynamodb:CreateTable",
          "dynamodb:DeleteTable",
          "dynamodb:UpdateTable",
          "dynamodb:UpdateContinuousBackups",
          "dynamodb:UpdateTimeToLive",
          "dynamodb:TagResource",
          "dynamodb:UntagResource",
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:*:table/${var.project}-*"
      },

      # ----------------------------------------------------------
      # EventBridge Scheduler — read-only
      # ----------------------------------------------------------
      {
        Sid    = "SchedulerRead"
        Effect = "Allow"
        Action = [
          "scheduler:GetSchedule",
          "scheduler:GetScheduleGroup",
          "scheduler:ListSchedules",
          "scheduler:ListScheduleGroups",
          "scheduler:ListTagsForResource",
        ]
        Resource = "*"
      },

      # ----------------------------------------------------------
      # EventBridge Scheduler — write (scoped to project prefix)
      # ----------------------------------------------------------
      {
        Sid    = "SchedulerWrite"
        Effect = "Allow"
        Action = [
          "scheduler:CreateSchedule",
          "scheduler:DeleteSchedule",
          "scheduler:UpdateSchedule",
          "scheduler:CreateScheduleGroup",
          "scheduler:DeleteScheduleGroup",
          "scheduler:TagResource",
          "scheduler:UntagResource",
        ]
        Resource = [
          "arn:aws:scheduler:${var.aws_region}:*:schedule/${var.project}-*/*",
          "arn:aws:scheduler:${var.aws_region}:*:schedule-group/${var.project}-*",
        ]
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "tfc_serverless" {
  role       = aws_iam_role.tfc.name
  policy_arn = aws_iam_policy.tfc_serverless.arn
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
