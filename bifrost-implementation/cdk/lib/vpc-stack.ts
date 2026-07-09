import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

export class BifrostVpcStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;
  public readonly albSecurityGroup: ec2.SecurityGroup;
  public readonly ecsSecurityGroup: ec2.SecurityGroup;
  public readonly efsSecurityGroup: ec2.SecurityGroup;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ── VPC with 2 AZs, public + private subnets ──────────────────────────
    this.vpc = new ec2.Vpc(this, 'BifrostVpc', {
      maxAzs: 2,
      ipAddresses: ec2.IpAddresses.cidr('10.10.0.0/16'),
      natGateways: 2,
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: 'Private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
      ],
    });
    cdk.Tags.of(this.vpc).add('Name', 'bifrost-vpc');

    // ── Security Groups ───────────────────────────────────────────────────

    // ALB: accepts traffic from CloudFront managed prefix list
    this.albSecurityGroup = new ec2.SecurityGroup(this, 'AlbSg', {
      vpc: this.vpc,
      description: 'ALB - accepts only CloudFront VPC Origin traffic',
      allowAllOutbound: true,
    });
    // CloudFront managed prefix list (us-east-1: pl-3b927c52)
    // Using ManagedPrefixList for other regions dynamically
    this.albSecurityGroup.addIngressRule(
      ec2.Peer.ipv4(this.vpc.vpcCidrBlock),
      ec2.Port.tcp(80),
      'Internal VPC access (CloudFront VPC Origin)',
    );
    cdk.Tags.of(this.albSecurityGroup).add('Name', 'bifrost-alb-sg');

    // ECS: accepts traffic from ALB only
    this.ecsSecurityGroup = new ec2.SecurityGroup(this, 'EcsSg', {
      vpc: this.vpc,
      description: 'ECS Fargate - accepts only ALB traffic on 8080',
      allowAllOutbound: true,
    });
    this.ecsSecurityGroup.addIngressRule(
      this.albSecurityGroup,
      ec2.Port.tcp(8080),
      'Bifrost HTTP from ALB',
    );
    cdk.Tags.of(this.ecsSecurityGroup).add('Name', 'bifrost-ecs-sg');

    // EFS: accepts NFS from ECS only
    this.efsSecurityGroup = new ec2.SecurityGroup(this, 'EfsSg', {
      vpc: this.vpc,
      description: 'EFS - accepts NFS from ECS tasks only',
      allowAllOutbound: false,
    });
    this.efsSecurityGroup.addIngressRule(
      this.ecsSecurityGroup,
      ec2.Port.tcp(2049),
      'NFS from ECS tasks',
    );
    cdk.Tags.of(this.efsSecurityGroup).add('Name', 'bifrost-efs-sg');

    // ── Outputs ───────────────────────────────────────────────────────────
    new cdk.CfnOutput(this, 'VpcId', {
      value: this.vpc.vpcId,
      description: 'Bifrost VPC ID',
      exportName: 'BifrostVpcId',
    });
  }
}
