/**
 * OPTIONAL STACK: Amazon Managed Grafana + Amazon Managed Prometheus
 *
 * Skip this stack by setting SKIP_GRAFANA=true or passing --context skipGrafana=true
 *
 * Prerequisites:
 * - AWS IAM Identity Center (SSO) must be enabled in your account
 * - Run: aws sso-admin list-instances to confirm it's enabled
 *
 * After deployment:
 * 1. Go to Grafana URL in outputs
 * 2. Log in with your SSO credentials
 * 3. The CloudWatch datasource is pre-configured
 * 4. The Bifrost dashboard is automatically provisioned
 */

import * as cdk from 'aws-cdk-lib';
import * as amp from 'aws-cdk-lib/aws-aps';
import * as grafana from 'aws-cdk-lib/aws-grafana';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export interface BifrostGrafanaStackProps extends cdk.StackProps {
  adminEmail: string;
  bifrostTaskRole: iam.Role;
}

export class BifrostGrafanaStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: BifrostGrafanaStackProps) {
    super(scope, id, props);

    const { adminEmail, bifrostTaskRole } = props;

    // ── Amazon Managed Prometheus workspace ──────────────────────────────
    const ampWorkspace = new amp.CfnWorkspace(this, 'AMPWorkspace', {
      alias: 'bifrost-gateway',
      tags: [{ key: 'auto-delete', value: 'no' }, { key: 'project', value: 'bifrost-gateway' }],
    });

    // Allow Bifrost ECS task to remote_write to AMP
    bifrostTaskRole.addToPolicy(new iam.PolicyStatement({
      actions: ['aps:RemoteWrite', 'aps:GetSeries', 'aps:GetLabels', 'aps:GetMetricMetadata'],
      resources: [ampWorkspace.attrArn],
    }));

    // ── IAM role for Grafana ──────────────────────────────────────────────
    const grafanaRole = new iam.Role(this, 'GrafanaRole', {
      roleName: 'bifrost-grafana-role',
      assumedBy: new iam.ServicePrincipal('grafana.amazonaws.com'),
      inlinePolicies: {
        CloudWatchRead: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: [
                'cloudwatch:DescribeAlarmsForMetric',
                'cloudwatch:DescribeAlarmHistory',
                'cloudwatch:DescribeAlarms',
                'cloudwatch:ListMetrics',
                'cloudwatch:GetMetricData',
                'cloudwatch:GetInsightRuleReport',
              ],
              resources: ['*'],
            }),
            new iam.PolicyStatement({
              actions: [
                'logs:DescribeLogGroups',
                'logs:GetLogGroupFields',
                'logs:StartQuery',
                'logs:StopQuery',
                'logs:GetQueryResults',
                'logs:GetLogEvents',
              ],
              resources: ['*'],
            }),
            new iam.PolicyStatement({
              actions: [
                'ec2:DescribeTags',
                'ec2:DescribeInstances',
                'ec2:DescribeRegions',
              ],
              resources: ['*'],
            }),
            new iam.PolicyStatement({
              actions: ['xray:BatchGetTraces', 'xray:GetTraceSummaries'],
              resources: ['*'],
            }),
          ],
        }),
        AMPRead: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: [
                'aps:ListWorkspaces',
                'aps:DescribeWorkspace',
                'aps:QueryMetrics',
                'aps:GetLabels',
                'aps:GetSeries',
                'aps:GetMetricMetadata',
              ],
              resources: ['*'],
            }),
          ],
        }),
      },
    });

    // ── Amazon Managed Grafana workspace ─────────────────────────────────
    const grafanaWorkspace = new grafana.CfnWorkspace(this, 'GrafanaWorkspace', {
      name: 'bifrost-gateway',
      description: 'Bifrost AI Gateway Observability — team metrics, token consumption, quota tracking',
      accountAccessType: 'CURRENT_ACCOUNT',
      authenticationProviders: ['AWS_SSO'],
      permissionType: 'CUSTOMER_MANAGED',
      roleArn: grafanaRole.roleArn,
      dataSources: ['CLOUDWATCH', 'PROMETHEUS', 'XRAY'],
      notificationDestinations: ['SNS'],
      pluginAdminEnabled: false,
      tags: [{ key: 'auto-delete', value: 'no' }, { key: 'project', value: 'bifrost-gateway' }],
    });

    // ── Outputs ───────────────────────────────────────────────────────────
    new cdk.CfnOutput(this, 'GrafanaUrl', {
      value: `https://${grafanaWorkspace.attrEndpoint}`,
      description: '📈 Amazon Managed Grafana URL',
    });

    new cdk.CfnOutput(this, 'AMPEndpoint', {
      value: ampWorkspace.attrPrometheusEndpoint,
      description: 'Amazon Managed Prometheus remote_write endpoint',
      exportName: 'BifrostAMPEndpoint',
    });

    new cdk.CfnOutput(this, 'AMPWorkspaceId', {
      value: ampWorkspace.ref,
      description: 'AMP Workspace ID',
    });

    new cdk.CfnOutput(this, 'GrafanaWorkspaceId', {
      value: grafanaWorkspace.ref,
      description: 'Grafana Workspace ID',
    });

    new cdk.CfnOutput(this, 'HowToAddGrafanaUser', {
      value: `aws grafana create-workspace-user --workspace-id ${grafanaWorkspace.ref} --user-id YOUR_SSO_USER_ID --role ADMIN --region ${this.region}`,
      description: 'Command to add yourself as a Grafana admin (get SSO user ID from IAM Identity Center console)',
    });

    new cdk.CfnOutput(this, 'PostDeployNote', {
      value: 'After deployment: 1) Add yourself as Grafana admin 2) Open Grafana URL 3) Dashboard is auto-provisioned from CloudWatch',
      description: 'Post-deployment steps for Grafana',
    });
  }
}
