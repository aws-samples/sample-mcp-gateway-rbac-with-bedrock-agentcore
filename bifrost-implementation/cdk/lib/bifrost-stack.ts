import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as efs from 'aws-cdk-lib/aws-efs';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as ssm from 'aws-cdk-lib/aws-secretsmanager';
import * as crypto from 'crypto';
import { Construct } from 'constructs';

export interface BifrostStackProps extends cdk.StackProps {
  vpc: ec2.Vpc;
  albSecurityGroup: ec2.SecurityGroup;
  ecsSecurityGroup: ec2.SecurityGroup;
  efsSecurityGroup: ec2.SecurityGroup;
  bifrostVersion?: string;
  dailyTokenLimitAlpha?: number;
  dailyTokenLimitBeta?: number;
}

export class BifrostStack extends cdk.Stack {
  public readonly alb: elbv2.ApplicationLoadBalancer;
  public readonly taskRole: iam.Role;
  public readonly artifactBucket: s3.Bucket;
  public readonly clusterArn: string;

  constructor(scope: Construct, id: string, props: BifrostStackProps) {
    super(scope, id, props);

    const {
      vpc,
      albSecurityGroup,
      ecsSecurityGroup,
      efsSecurityGroup,
      bifrostVersion = 'latest',
      dailyTokenLimitAlpha = 100000,
      dailyTokenLimitBeta = 50000,
    } = props;

    // ── S3 Artifact Bucket ────────────────────────────────────────────────
    this.artifactBucket = new s3.Bucket(this, 'ArtifactBucket', {
      bucketName: `bifrost-artifacts-${this.account}-${this.region}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      versioned: false,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ── EFS for Bifrost config persistence ───────────────────────────────
    const filesystem = new efs.FileSystem(this, 'BifrostEfs', {
      vpc,
      securityGroup: efsSecurityGroup,
      encrypted: true,
      performanceMode: efs.PerformanceMode.GENERAL_PURPOSE,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const accessPoint = filesystem.addAccessPoint('BifrostAccessPoint', {
      path: '/bifrost-data',
      createAcl: { ownerGid: '1000', ownerUid: '1000', permissions: '755' },
      posixUser: { gid: '1000', uid: '1000' },
    });

    // ── Encryption key for Bifrost (auto-generated, stored in Secrets Manager)
    const encryptionKey = new ssm.Secret(this, 'BifrostEncryptionKey', {
      secretName: '/bifrost/encryption-key',
      description: 'Auto-generated 32-char encryption key for Bifrost config store',
      generateSecretString: {
        secretStringTemplate: '{}',
        generateStringKey: 'key',
        passwordLength: 32,
        excludePunctuation: true,
      },
    });

    // ── CloudWatch Log Groups ─────────────────────────────────────────────
    const bifrostLogGroup = new logs.LogGroup(this, 'BifrostLogGroup', {
      logGroupName: '/bifrost/container',
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const accessLogGroup = new logs.LogGroup(this, 'AccessLogGroup', {
      logGroupName: '/bifrost/access',
      retention: logs.RetentionDays.THREE_MONTHS,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    new logs.LogGroup(this, 'AuditLogGroup', {
      logGroupName: '/bifrost/audit',
      retention: logs.RetentionDays.ONE_YEAR,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ── IAM Roles ─────────────────────────────────────────────────────────
    const executionRole = new iam.Role(this, 'EcsExecutionRole', {
      roleName: 'bifrost-ecs-execution-role',
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AmazonECSTaskExecutionRolePolicy'),
      ],
    });

    // Allow execution role to read secrets
    encryptionKey.grantRead(executionRole);

    this.taskRole = new iam.Role(this, 'EcsTaskRole', {
      roleName: 'bifrost-ecs-task-role',
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      inlinePolicies: {
        BedrockAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
              resources: [
                `arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku*`,
                `arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet*`,
                `arn:aws:bedrock:*::foundation-model/anthropic.claude-opus*`,
                `arn:aws:bedrock:${this.region}:${this.account}:inference-profile/us.anthropic.claude-haiku*`,
                `arn:aws:bedrock:${this.region}:${this.account}:inference-profile/us.anthropic.claude-sonnet*`,
                `arn:aws:bedrock:${this.region}:${this.account}:inference-profile/us.anthropic.claude-opus*`,
              ],
            }),
            new iam.PolicyStatement({
              actions: ['bedrock:ListFoundationModels', 'bedrock:GetFoundationModel'],
              resources: ['*'],
            }),
          ],
        }),
        CloudWatchAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: [
                'cloudwatch:PutMetricData',
                'logs:CreateLogStream',
                'logs:PutLogEvents',
                'logs:CreateLogGroup',
                'logs:DescribeLogGroups',
                'logs:DescribeLogStreams',
              ],
              resources: ['*'],
            }),
            new iam.PolicyStatement({
              actions: [
                'xray:PutTraceSegments',
                'xray:PutTelemetryRecords',
                'xray:GetSamplingRules',
                'xray:GetSamplingTargets',
              ],
              resources: ['*'],
            }),
          ],
        }),
        S3Access: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: ['s3:GetObject'],
              resources: [`${this.artifactBucket.bucketArn}/*`],
            }),
          ],
        }),
        EfsAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: [
                'elasticfilesystem:ClientMount',
                'elasticfilesystem:ClientWrite',
                'elasticfilesystem:DescribeMountTargets',
              ],
              resources: [filesystem.fileSystemArn],
            }),
          ],
        }),
        // AMP remote write (for OTEL → Prometheus)
        AMPAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: [
                'aps:RemoteWrite',
                'aps:GetSeries',
                'aps:GetLabels',
                'aps:GetMetricMetadata',
              ],
              resources: ['*'],
            }),
          ],
        }),
      },
    });

    // ── ECS Cluster ───────────────────────────────────────────────────────
    const cluster = new ecs.Cluster(this, 'BifrostCluster', {
      clusterName: 'bifrost-cluster',
      vpc,
      containerInsights: true,
    });
    this.clusterArn = cluster.clusterArn;

    // ── Task Definition ───────────────────────────────────────────────────
    const taskDef = new ecs.FargateTaskDefinition(this, 'BifrostTaskDef', {
      family: 'bifrost-task',
      cpu: 1024,
      memoryLimitMiB: 3072,
      executionRole,
      taskRole: this.taskRole,
    });

    // EFS volume
    taskDef.addVolume({
      name: 'bifrost-data',
      efsVolumeConfiguration: {
        fileSystemId: filesystem.fileSystemId,
        transitEncryption: 'ENABLED',
        authorizationConfig: {
          accessPointId: accessPoint.accessPointId,
          iam: 'ENABLED',
        },
      },
    });

    // Bifrost container
    const bifrostContainer = taskDef.addContainer('bifrost', {
      image: ecs.ContainerImage.fromRegistry(`maximhq/bifrost:${bifrostVersion}`),
      essential: true,
      command: ['-host', '0.0.0.0', '-port', '8080', '-app-dir', '/app/data'],
      portMappings: [{ containerPort: 8080, protocol: ecs.Protocol.TCP }],
      environment: {
        BIFROST_HOST: '0.0.0.0',
        APP_PORT: '8080',
        LOG_LEVEL: 'info',
        LOG_STYLE: 'json',
        TEAM_ALPHA_DAILY_LIMIT: String(dailyTokenLimitAlpha),
        TEAM_BETA_DAILY_LIMIT: String(dailyTokenLimitBeta),
        MONTHLY_TOKEN_LIMIT: '2000000',
        OTEL_SERVICE_NAME: 'bifrost-gateway',
      },
      secrets: {
        BIFROST_ENCRYPTION_KEY: ecs.Secret.fromSecretsManager(encryptionKey, 'key'),
      },
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: 'bifrost',
        logGroup: bifrostLogGroup,
      }),
      healthCheck: {
        command: ['CMD-SHELL', 'wget -qO- http://localhost:8080/health || exit 1'],
        interval: cdk.Duration.seconds(30),
        timeout: cdk.Duration.seconds(10),
        retries: 3,
        startPeriod: cdk.Duration.seconds(90),
      },
      ulimits: [{ name: ecs.UlimitName.NOFILE, softLimit: 65536, hardLimit: 65536 }],
    });

    bifrostContainer.addMountPoints({
      containerPath: '/app/data',
      sourceVolume: 'bifrost-data',
      readOnly: false,
    });

    // ── Internal ALB ──────────────────────────────────────────────────────
    this.alb = new elbv2.ApplicationLoadBalancer(this, 'BifrostAlb', {
      loadBalancerName: 'bifrost-alb',
      vpc,
      internetFacing: false,  // Internal only — CloudFront accesses via VPC Origin
      securityGroup: albSecurityGroup,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
    });

    const targetGroup = new elbv2.ApplicationTargetGroup(this, 'BifrostTg', {
      targetGroupName: 'bifrost-tg',
      vpc,
      port: 8080,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targetType: elbv2.TargetType.IP,
      healthCheck: {
        path: '/health',
        interval: cdk.Duration.seconds(30),
        timeout: cdk.Duration.seconds(10),
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 3,
      },
      stickinessCookieDuration: cdk.Duration.days(1),
    });

    this.alb.addListener('BifrostListener', {
      port: 80,
      protocol: elbv2.ApplicationProtocol.HTTP,
      defaultTargetGroups: [targetGroup],
    });

    // ── ECS Service ───────────────────────────────────────────────────────
    const service = new ecs.FargateService(this, 'BifrostService', {
      serviceName: 'bifrost-service',
      cluster,
      taskDefinition: taskDef,
      desiredCount: 1,
      assignPublicIp: false,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      securityGroups: [ecsSecurityGroup],
      enableExecuteCommand: true,  // Allows ECS Exec for debugging
      circuitBreaker: { rollback: true },
      healthCheckGracePeriod: cdk.Duration.seconds(90),
    });

    service.attachToApplicationTargetGroup(targetGroup);

    // ── Outputs ───────────────────────────────────────────────────────────
    new cdk.CfnOutput(this, 'AlbDnsName', {
      value: this.alb.loadBalancerDnsName,
      description: 'Internal ALB DNS name (for CloudFront VPC Origin)',
      exportName: 'BifrostAlbDnsName',
    });

    new cdk.CfnOutput(this, 'ArtifactBucketName', {
      value: this.artifactBucket.bucketName,
      description: 'S3 bucket for Bifrost artifacts',
      exportName: 'BifrostArtifactBucket',
    });

    new cdk.CfnOutput(this, 'ClusterName', {
      value: cluster.clusterName,
      description: 'ECS cluster name',
    });

    new cdk.CfnOutput(this, 'AccessLogGroupName', {
      value: accessLogGroup.logGroupName,
      description: 'CloudWatch log group for Bifrost access logs',
      exportName: 'BifrostAccessLogGroup',
    });
  }
}
