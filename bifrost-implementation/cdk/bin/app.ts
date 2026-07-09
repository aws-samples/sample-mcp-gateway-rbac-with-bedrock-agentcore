#!/usr/bin/env node
/**
 * Bifrost AI Gateway — CDK Application Entry Point
 *
 * Stacks (all optional via environment flags):
 *   BifrostVpcStack           - VPC, subnets, NAT gateways, security groups
 *   BifrostStack              - ECS Fargate, ALB, EFS, IAM roles
 *   BifrostCloudfrontStack    - CloudFront + Cognito + S3 (skip: SKIP_CLOUDFRONT=true)
 *   BifrostObservabilityStack - CloudWatch dashboard, alarms, quota publisher
 *   BifrostGrafanaStack       - Amazon Managed Grafana + AMP (skip: SKIP_GRAFANA=true)
 *
 * Usage:
 *   npx cdk deploy --all                    # Deploy everything
 *   npx cdk deploy BifrostVpcStack BifrostStack  # Core only
 *   SKIP_GRAFANA=true npx cdk deploy --all  # Skip Grafana
 *
 * Configuration (via environment variables or cdk.context.json):
 *   ADMIN_EMAIL      - Email for Cognito admin + alarm notifications (required)
 *   BIFROST_VERSION  - Bifrost Docker image tag (default: latest)
 *   DEPLOY_REGION    - AWS region (default: us-east-1)
 */

import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { BifrostVpcStack } from '../lib/vpc-stack';
import { BifrostStack } from '../lib/bifrost-stack';
import { BifrostCloudfrontStack } from '../lib/cloudfront-stack';
import { BifrostObservabilityStack } from '../lib/observability-stack';
import { BifrostGrafanaStack } from '../lib/grafana-stack';

const app = new cdk.App();

// ── Read configuration ───────────────────────────────────────────────────────
const adminEmail = app.node.tryGetContext('adminEmail')
  || process.env.ADMIN_EMAIL
  || 'admin@example.com';

const bifrostVersion = app.node.tryGetContext('bifrostVersion')
  || process.env.BIFROST_VERSION
  || 'latest';

const deployRegion = app.node.tryGetContext('deployRegion')
  || process.env.DEPLOY_REGION
  || process.env.CDK_DEFAULT_REGION
  || 'us-east-1';

const deployAccount = process.env.CDK_DEFAULT_ACCOUNT;

const skipCloudFront = (app.node.tryGetContext('skipCloudFront') || process.env.SKIP_CLOUDFRONT) === 'true';
const skipGrafana = (app.node.tryGetContext('skipGrafana') || process.env.SKIP_GRAFANA) === 'true';

const dailyTokenLimitAlpha = Number(app.node.tryGetContext('dailyTokenLimitAlpha') || process.env.DAILY_TOKEN_LIMIT_ALPHA || '100000');
const dailyTokenLimitBeta = Number(app.node.tryGetContext('dailyTokenLimitBeta') || process.env.DAILY_TOKEN_LIMIT_BETA || '50000');

const env: cdk.Environment = {
  account: deployAccount,
  region: deployRegion,
};

const commonProps = {
  env,
  tags: {
    Project: 'bifrost-gateway',
    'auto-delete': 'no',
    ManagedBy: 'CDK',
  },
};

// ── Stack 1: VPC ─────────────────────────────────────────────────────────────
const vpcStack = new BifrostVpcStack(app, 'BifrostVpcStack', {
  ...commonProps,
  description: 'Bifrost AI Gateway — VPC, subnets, NAT gateways, security groups',
});

// ── Stack 2: Bifrost Core (ECS + ALB) ────────────────────────────────────────
const bifrostStack = new BifrostStack(app, 'BifrostStack', {
  ...commonProps,
  description: 'Bifrost AI Gateway — ECS Fargate service, internal ALB, EFS, IAM roles',
  vpc: vpcStack.vpc,
  albSecurityGroup: vpcStack.albSecurityGroup,
  ecsSecurityGroup: vpcStack.ecsSecurityGroup,
  efsSecurityGroup: vpcStack.efsSecurityGroup,
  bifrostVersion,
  dailyTokenLimitAlpha,
  dailyTokenLimitBeta,
});
bifrostStack.addDependency(vpcStack);

// ── Stack 3: CloudFront (optional) ───────────────────────────────────────────
let cfStack: BifrostCloudfrontStack | undefined;
if (!skipCloudFront) {
  cfStack = new BifrostCloudfrontStack(app, 'BifrostCloudfrontStack', {
    ...commonProps,
    description: 'Bifrost AI Gateway — CloudFront VPC Origin, Cognito admin auth, S3 chatbox',
    alb: bifrostStack.alb,
    adminEmail,
  });
  cfStack.addDependency(bifrostStack);
}

// ── Stack 4: Observability ───────────────────────────────────────────────────
const obsStack = new BifrostObservabilityStack(app, 'BifrostObservabilityStack', {
  ...commonProps,
  description: 'Bifrost AI Gateway — CloudWatch dashboard, alarms, quota publisher Lambda',
  alarmEmail: adminEmail,
  artifactBucket: bifrostStack.artifactBucket,
  dailyTokenLimitAlpha,
  dailyTokenLimitBeta,
});
obsStack.addDependency(bifrostStack);

// ── Stack 5: Grafana (optional) ──────────────────────────────────────────────
if (!skipGrafana) {
  const grafanaStack = new BifrostGrafanaStack(app, 'BifrostGrafanaStack', {
    ...commonProps,
    description: 'Bifrost AI Gateway — Amazon Managed Grafana + Prometheus (optional)',
    adminEmail,
    bifrostTaskRole: bifrostStack.taskRole,
  });
  grafanaStack.addDependency(obsStack);
}

app.synth();
