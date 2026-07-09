import * as cdk from 'aws-cdk-lib';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import { Construct } from 'constructs';

export interface BifrostCloudfrontStackProps extends cdk.StackProps {
  alb: elbv2.ApplicationLoadBalancer;
  adminEmail: string;
}

export class BifrostCloudfrontStack extends cdk.Stack {
  public readonly distributionDomainName: string;
  public readonly chatboxBucket: s3.Bucket;
  public readonly userPoolId: string;

  constructor(scope: Construct, id: string, props: BifrostCloudfrontStackProps) {
    super(scope, id, props);

    const { alb, adminEmail } = props;

    // ── S3 Bucket for chatbox static frontend ─────────────────────────────
    this.chatboxBucket = new s3.Bucket(this, 'ChatboxBucket', {
      bucketName: `bifrost-chatbox-${this.account}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ── CloudFront Origin Access Control for S3 ───────────────────────────
    const oac = new cloudfront.S3OriginAccessControl(this, 'S3OAC', {
      description: 'OAC for Bifrost chatbox S3 bucket',
    });

    // ── Cognito User Pool for Admin UI protection ─────────────────────────
    const userPool = new cognito.UserPool(this, 'AdminUserPool', {
      userPoolName: 'bifrost-admin-pool',
      selfSignUpEnabled: false,  // Admin-only: use console to add users
      signInAliases: { email: true },
      autoVerify: { email: true },
      passwordPolicy: {
        minLength: 12,
        requireUppercase: true,
        requireLowercase: true,
        requireDigits: true,
        requireSymbols: true,
      },
      userInvitation: {
        emailSubject: 'Bifrost AI Gateway Admin Access',
        emailBody: `You have been granted admin access to the Bifrost AI Gateway.

Username: {username}
Temporary password: {####}

Sign in at: https://DISTRIBUTION_URL/

This password expires in 7 days.`,
      },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });
    this.userPoolId = userPool.userPoolId;

    // User pool domain for hosted UI
    const userPoolDomain = userPool.addDomain('AdminDomain', {
      cognitoDomain: {
        domainPrefix: `bifrost-admin-${this.account}`,
      },
    });

    // Initial admin user (invited by email)
    new cognito.CfnUserPoolUser(this, 'AdminUser', {
      userPoolId: userPool.userPoolId,
      username: adminEmail,
      desiredDeliveryMediums: ['EMAIL'],
      userAttributes: [
        { name: 'email', value: adminEmail },
        { name: 'email_verified', value: 'true' },
      ],
    });

    // ── CloudFront VPC Origin for ALB ─────────────────────────────────────
    // NOTE: CloudFront VPC Origins allow CloudFront to reach internal ALBs
    // The VPC Origin is created separately as it requires the ALB ARN
    // and cannot be created inline in CloudFront distribution easily.
    // We use HTTP-only to the ALB (CloudFront handles HTTPS termination).

    const albOrigin = new origins.HttpOrigin(alb.loadBalancerDnsName, {
      protocolPolicy: cloudfront.OriginProtocolPolicy.HTTP_ONLY,
      readTimeout: cdk.Duration.seconds(60),
      keepaliveTimeout: cdk.Duration.seconds(60),
    });

    const s3Origin = origins.S3BucketOrigin.withOriginAccessControl(this.chatboxBucket, {
      originAccessControl: oac,
    });

    // ── CloudFront Functions ──────────────────────────────────────────────

    // Block /metrics endpoint
    const blockMetricsFn = new cloudfront.Function(this, 'BlockMetricsFn', {
      functionName: 'bifrost-block-metrics',
      code: cloudfront.FunctionCode.fromInline(`
function handler(event) {
  return {
    statusCode: 403,
    statusDescription: 'Forbidden',
    headers: { 'content-type': { value: 'application/json' } },
    body: '{"error":"Access denied"}'
  };
}
`),
      runtime: cloudfront.FunctionRuntime.JS_2_0,
      comment: 'Block direct access to Prometheus /metrics endpoint',
    });

    // ── CloudFront Distribution ───────────────────────────────────────────
    const distribution = new cloudfront.Distribution(this, 'BifrostCF', {
      comment: 'Bifrost AI Gateway',
      httpVersion: cloudfront.HttpVersion.HTTP2_AND_3,
      priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
      enableIpv6: true,

      // Default behavior → Bifrost admin UI (ALB via VPC Origin)
      defaultBehavior: {
        origin: albOrigin,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
        cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
        originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER,
        responseHeadersPolicy: cloudfront.ResponseHeadersPolicy.SECURITY_HEADERS,
        compress: true,
      },

      additionalBehaviors: {
        // /v1/* → Bifrost API (no caching)
        '/v1/*': {
          origin: albOrigin,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER,
          responseHeadersPolicy: cloudfront.ResponseHeadersPolicy.SECURITY_HEADERS,
          compress: false,
        },
        // /health → ALB health check
        '/health': {
          origin: albOrigin,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
        },
        // /chat.html → S3 chatbox
        '/chat.html': {
          origin: s3Origin,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
          compress: true,
        },
        // /metrics* → blocked
        '/metrics*': {
          origin: s3Origin,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          functionAssociations: [{
            function: blockMetricsFn,
            eventType: cloudfront.FunctionEventType.VIEWER_REQUEST,
          }],
        },
      },

      // CloudFront access log bucket (auto-created)
      enableLogging: true,
      logFilePrefix: 'cloudfront/',
    });

    this.distributionDomainName = distribution.distributionDomainName;

    // ── Update Cognito App Client with real callback URLs ─────────────────
    const appClient = userPool.addClient('CloudFrontClient', {
      userPoolClientName: 'bifrost-cloudfront-client',
      generateSecret: true,
      oAuth: {
        flows: { authorizationCodeGrant: true },
        scopes: [cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
        callbackUrls: [
          `https://${distribution.distributionDomainName}`,
          `https://${distribution.distributionDomainName}/`,
        ],
        logoutUrls: [
          `https://${distribution.distributionDomainName}`,
        ],
      },
      supportedIdentityProviders: [cognito.UserPoolClientIdentityProvider.COGNITO],
      preventUserExistenceErrors: true,
    });

    // ── Upload placeholder chatbox.html to S3 ─────────────────────────────
    // The deploy script will patch and re-upload with live values
    new s3deploy.BucketDeployment(this, 'ChatboxDeploy', {
      sources: [s3deploy.Source.asset('../chatbox')],
      destinationBucket: this.chatboxBucket,
      distribution,
      distributionPaths: ['/chat.html', '/chatbox.html'],
    });

    // ── Outputs ───────────────────────────────────────────────────────────
    new cdk.CfnOutput(this, 'ChatUrl', {
      value: `https://${distribution.distributionDomainName}/chat.html`,
      description: '💬 Chat UI URL — open this in your browser',
    });

    new cdk.CfnOutput(this, 'AdminUiUrl', {
      value: `https://${distribution.distributionDomainName}`,
      description: '🚀 Bifrost Admin UI URL',
    });

    new cdk.CfnOutput(this, 'CognitoLoginUrl', {
      value: `https://${userPoolDomain.domainName}.auth.${this.region}.amazoncognito.com/login?client_id=${appClient.userPoolClientId}&response_type=code&scope=openid+email+profile&redirect_uri=https://${distribution.distributionDomainName}`,
      description: 'Direct Cognito login URL for admin UI',
    });

    new cdk.CfnOutput(this, 'CognitoUserPoolId', {
      value: userPool.userPoolId,
      description: 'Cognito User Pool ID (add users via: aws cognito-idp admin-create-user)',
      exportName: 'BifrostCognitoPoolId',
    });

    new cdk.CfnOutput(this, 'ChatboxBucketName', {
      value: this.chatboxBucket.bucketName,
      description: 'S3 bucket for chatbox static files',
      exportName: 'BifrostChatboxBucket',
    });

    new cdk.CfnOutput(this, 'CloudFrontDistributionId', {
      value: distribution.distributionId,
      description: 'CloudFront distribution ID',
      exportName: 'BifrostCFDistributionId',
    });

    new cdk.CfnOutput(this, 'HowToAddUsers', {
      value: `aws cognito-idp admin-create-user --user-pool-id ${userPool.userPoolId} --username USER@EMAIL.COM --user-attributes Name=email,Value=USER@EMAIL.COM Name=email_verified,Value=true --desired-delivery-mediums EMAIL --region ${this.region}`,
      description: 'Command to add new admin users to Cognito',
    });
  }
}
