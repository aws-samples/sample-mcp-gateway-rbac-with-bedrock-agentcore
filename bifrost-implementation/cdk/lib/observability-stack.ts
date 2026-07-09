import * as cdk from 'aws-cdk-lib';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as cloudwatchActions from 'aws-cdk-lib/aws-cloudwatch-actions';
import * as events from 'aws-cdk-lib/aws-events';
import * as eventsTargets from 'aws-cdk-lib/aws-events-targets';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as snsSubscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as path from 'path';
import { Construct } from 'constructs';

export interface BifrostObservabilityStackProps extends cdk.StackProps {
  alarmEmail: string;
  artifactBucket: s3.Bucket;
  dailyTokenLimitAlpha?: number;
  dailyTokenLimitBeta?: number;
}

export class BifrostObservabilityStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: BifrostObservabilityStackProps) {
    super(scope, id, props);

    const {
      alarmEmail,
      artifactBucket,
      dailyTokenLimitAlpha = 100000,
      dailyTokenLimitBeta = 50000,
    } = props;

    const NAMESPACE = 'Bifrost/Gateway';

    // ── SNS Topic for alarms ──────────────────────────────────────────────
    const alarmTopic = new sns.Topic(this, 'AlarmTopic', {
      topicName: 'bifrost-alarms',
      displayName: 'Bifrost Gateway Alarms',
    });
    alarmTopic.addSubscription(new snsSubscriptions.EmailSubscription(alarmEmail));

    // ── Extra log group for metrics ───────────────────────────────────────
    new logs.LogGroup(this, 'MetricsLogGroup', {
      logGroupName: '/bifrost/metrics',
      retention: logs.RetentionDays.TWO_WEEKS,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ── Metric Filters on /bifrost/access logs ────────────────────────────
    const accessLogGroup = logs.LogGroup.fromLogGroupName(
      this, 'AccessLogGroupRef', '/bifrost/access',
    );

    // Request count by team
    new logs.MetricFilter(this, 'RequestFilter', {
      logGroup: accessLogGroup,
      filterPattern: logs.FilterPattern.exists('$.team'),
      metricNamespace: NAMESPACE,
      metricName: 'RequestCount',
      metricValue: '1',
      unit: cloudwatch.Unit.COUNT,
      dimensions: { team: '$.team' },
    });

    // Token input by team
    new logs.MetricFilter(this, 'TokenInputFilter', {
      logGroup: accessLogGroup,
      filterPattern: logs.FilterPattern.numberValue('$.input_tokens', '>', 0),
      metricNamespace: NAMESPACE,
      metricName: 'TokensInput',
      metricValue: '$.input_tokens',
      unit: cloudwatch.Unit.COUNT,
      dimensions: { team: '$.team' },
    });

    // Token output by team
    new logs.MetricFilter(this, 'TokenOutputFilter', {
      logGroup: accessLogGroup,
      filterPattern: logs.FilterPattern.numberValue('$.output_tokens', '>', 0),
      metricNamespace: NAMESPACE,
      metricName: 'TokensOutput',
      metricValue: '$.output_tokens',
      unit: cloudwatch.Unit.COUNT,
      dimensions: { team: '$.team' },
    });

    // Model denied
    new logs.MetricFilter(this, 'ModelDeniedFilter', {
      logGroup: accessLogGroup,
      filterPattern: logs.FilterPattern.stringValue('$.status', '=', 'model_denied'),
      metricNamespace: NAMESPACE,
      metricName: 'ModelAccessDenied',
      metricValue: '1',
      unit: cloudwatch.Unit.COUNT,
      dimensions: { team: '$.team' },
    });

    // Errors
    new logs.MetricFilter(this, 'ErrorFilter', {
      logGroup: accessLogGroup,
      filterPattern: logs.FilterPattern.stringValue('$.status', '=', 'error'),
      metricNamespace: NAMESPACE,
      metricName: 'Errors',
      metricValue: '1',
      unit: cloudwatch.Unit.COUNT,
    });

    // Latency
    new logs.MetricFilter(this, 'LatencyFilter', {
      logGroup: accessLogGroup,
      filterPattern: logs.FilterPattern.numberValue('$.latency_seconds', '>', 0),
      metricNamespace: NAMESPACE,
      metricName: 'LatencySeconds',
      metricValue: '$.latency_seconds',
      unit: cloudwatch.Unit.SECONDS,
    });

    // ── Lambda: Quota Publisher ───────────────────────────────────────────
    const quotaPublisherRole = new iam.Role(this, 'QuotaPublisherRole', {
      roleName: 'bifrost-quota-publisher-role',
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      inlinePolicies: {
        CloudWatchRW: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: ['cloudwatch:GetMetricData', 'cloudwatch:PutMetricData'],
              resources: ['*'],
            }),
            new iam.PolicyStatement({
              actions: ['logs:CreateLogStream', 'logs:PutLogEvents'],
              resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:/aws/lambda/bifrost-quota-publisher:*`],
            }),
          ],
        }),
      },
    });

    const quotaPublisher = new lambda.Function(this, 'QuotaPublisher', {
      functionName: 'bifrost-quota-publisher',
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'lambda_function.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../scripts/quota-publisher')),
      role: quotaPublisherRole,
      timeout: cdk.Duration.seconds(60),
      environment: {
        NAMESPACE,
        TEAM_ALPHA_DAILY_LIMIT: String(dailyTokenLimitAlpha),
        TEAM_BETA_DAILY_LIMIT: String(dailyTokenLimitBeta),
        REGION: this.region,
      },
    });

    // Run every 5 minutes
    const rule = new events.Rule(this, 'QuotaSchedule', {
      ruleName: 'bifrost-quota-schedule',
      schedule: events.Schedule.rate(cdk.Duration.minutes(5)),
    });
    rule.addTarget(new eventsTargets.LambdaFunction(quotaPublisher));

    // ── CloudWatch Alarms ─────────────────────────────────────────────────

    const alphaQuota80 = new cloudwatch.Alarm(this, 'AlphaQuota80', {
      alarmName: 'bifrost-team-alpha-quota-80pct',
      alarmDescription: 'Team Alpha consumed 80% of daily token quota',
      metric: new cloudwatch.Metric({
        namespace: NAMESPACE,
        metricName: 'QuotaUtilisationPct',
        dimensionsMap: { team: 'team-alpha' },
        statistic: 'Maximum',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 80,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      evaluationPeriods: 1,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    alphaQuota80.addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    const alphaQuota100 = new cloudwatch.Alarm(this, 'AlphaQuota100', {
      alarmName: 'bifrost-team-alpha-quota-100pct',
      alarmDescription: 'Team Alpha daily token quota exhausted',
      metric: new cloudwatch.Metric({
        namespace: NAMESPACE,
        metricName: 'QuotaUtilisationPct',
        dimensionsMap: { team: 'team-alpha' },
        statistic: 'Maximum',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 100,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      evaluationPeriods: 1,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    alphaQuota100.addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    const betaQuota100 = new cloudwatch.Alarm(this, 'BetaQuota100', {
      alarmName: 'bifrost-team-beta-quota-100pct',
      alarmDescription: 'Team Beta daily token quota exhausted',
      metric: new cloudwatch.Metric({
        namespace: NAMESPACE,
        metricName: 'QuotaUtilisationPct',
        dimensionsMap: { team: 'team-beta' },
        statistic: 'Maximum',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 100,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      evaluationPeriods: 1,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    betaQuota100.addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    const highErrors = new cloudwatch.Alarm(this, 'HighErrors', {
      alarmName: 'bifrost-high-error-rate',
      alarmDescription: 'Bifrost error rate elevated',
      metric: new cloudwatch.Metric({
        namespace: NAMESPACE,
        metricName: 'Errors',
        statistic: 'Sum',
        period: cdk.Duration.minutes(5),
      }),
      threshold: 10,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      evaluationPeriods: 2,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    highErrors.addAlarmAction(new cloudwatchActions.SnsAction(alarmTopic));

    // ── CloudWatch Dashboard ──────────────────────────────────────────────
    const dashboard = new cloudwatch.Dashboard(this, 'BifrostDashboard', {
      dashboardName: 'bifrost-ai-gateway',
    });

    dashboard.addWidgets(
      new cloudwatch.TextWidget({
        markdown: `# ⚡ Bifrost AI Gateway — Live Observability\n**Namespace:** ${NAMESPACE} | **Region:** ${this.region}\n**Teams:** team-alpha (${dailyTokenLimitAlpha.toLocaleString()} tokens/day) · team-beta (${dailyTokenLimitBeta.toLocaleString()} tokens/day)`,
        width: 24,
        height: 2,
      }),
    );

    // Row 1: Summary stats
    dashboard.addWidgets(
      new cloudwatch.SingleValueWidget({
        title: 'Requests Today — Alpha',
        metrics: [new cloudwatch.Metric({ namespace: NAMESPACE, metricName: 'RequestCount', dimensionsMap: { team: 'team-alpha' }, statistic: 'Sum', period: cdk.Duration.days(1), label: 'Team Alpha' })],
        width: 6, height: 4,
      }),
      new cloudwatch.SingleValueWidget({
        title: 'Requests Today — Beta',
        metrics: [new cloudwatch.Metric({ namespace: NAMESPACE, metricName: 'RequestCount', dimensionsMap: { team: 'team-beta' }, statistic: 'Sum', period: cdk.Duration.days(1), label: 'Team Beta' })],
        width: 6, height: 4,
      }),
      new cloudwatch.SingleValueWidget({
        title: 'Model Denials Today',
        metrics: [new cloudwatch.Metric({ namespace: NAMESPACE, metricName: 'ModelAccessDenied', statistic: 'Sum', period: cdk.Duration.days(1) })],
        width: 6, height: 4,
      }),
      new cloudwatch.SingleValueWidget({
        title: 'Errors Today',
        metrics: [new cloudwatch.Metric({ namespace: NAMESPACE, metricName: 'Errors', statistic: 'Sum', period: cdk.Duration.days(1) })],
        width: 6, height: 4,
      }),
    );

    // Row 2: Quota gauges
    dashboard.addWidgets(
      new cloudwatch.GaugeWidget({
        title: 'Team Alpha — Quota %',
        metrics: [new cloudwatch.Metric({ namespace: NAMESPACE, metricName: 'QuotaUtilisationPct', dimensionsMap: { team: 'team-alpha' }, statistic: 'Maximum', period: cdk.Duration.minutes(5) })],
        leftYAxis: { min: 0, max: 100 },
        width: 12, height: 6,
      }),
      new cloudwatch.GaugeWidget({
        title: 'Team Beta — Quota %',
        metrics: [new cloudwatch.Metric({ namespace: NAMESPACE, metricName: 'QuotaUtilisationPct', dimensionsMap: { team: 'team-beta' }, statistic: 'Maximum', period: cdk.Duration.minutes(5) })],
        leftYAxis: { min: 0, max: 100 },
        width: 12, height: 6,
      }),
    );

    // Row 3: Time series
    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'Requests/min by Team',
        left: [
          new cloudwatch.Metric({ namespace: NAMESPACE, metricName: 'RequestCount', dimensionsMap: { team: 'team-alpha' }, statistic: 'Sum', period: cdk.Duration.minutes(1), label: 'Team Alpha' }),
          new cloudwatch.Metric({ namespace: NAMESPACE, metricName: 'RequestCount', dimensionsMap: { team: 'team-beta' }, statistic: 'Sum', period: cdk.Duration.minutes(1), label: 'Team Beta' }),
        ],
        width: 12, height: 6,
      }),
      new cloudwatch.GraphWidget({
        title: 'Token Consumption',
        left: [
          new cloudwatch.Metric({ namespace: NAMESPACE, metricName: 'TokensInput', dimensionsMap: { team: 'team-alpha' }, statistic: 'Sum', period: cdk.Duration.minutes(5), label: 'Alpha Input' }),
          new cloudwatch.Metric({ namespace: NAMESPACE, metricName: 'TokensOutput', dimensionsMap: { team: 'team-alpha' }, statistic: 'Sum', period: cdk.Duration.minutes(5), label: 'Alpha Output' }),
          new cloudwatch.Metric({ namespace: NAMESPACE, metricName: 'TokensInput', dimensionsMap: { team: 'team-beta' }, statistic: 'Sum', period: cdk.Duration.minutes(5), label: 'Beta Input' }),
          new cloudwatch.Metric({ namespace: NAMESPACE, metricName: 'TokensOutput', dimensionsMap: { team: 'team-beta' }, statistic: 'Sum', period: cdk.Duration.minutes(5), label: 'Beta Output' }),
        ],
        stacked: true,
        width: 12, height: 6,
      }),
    );

    // Row 4: Latency + alarms
    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title: 'Latency Percentiles (seconds)',
        left: [
          new cloudwatch.Metric({ namespace: NAMESPACE, metricName: 'LatencySeconds', statistic: 'p50', period: cdk.Duration.minutes(5), label: 'p50' }),
          new cloudwatch.Metric({ namespace: NAMESPACE, metricName: 'LatencySeconds', statistic: 'p95', period: cdk.Duration.minutes(5), label: 'p95' }),
          new cloudwatch.Metric({ namespace: NAMESPACE, metricName: 'LatencySeconds', statistic: 'p99', period: cdk.Duration.minutes(5), label: 'p99' }),
        ],
        width: 12, height: 6,
      }),
      new cloudwatch.AlarmStatusWidget({
        title: 'Active Alarms',
        alarms: [alphaQuota80, alphaQuota100, betaQuota100, highErrors],
        width: 12, height: 6,
      }),
    );

    // ── Outputs ───────────────────────────────────────────────────────────
    new cdk.CfnOutput(this, 'DashboardUrl', {
      value: `https://console.aws.amazon.com/cloudwatch/home?region=${this.region}#dashboards:name=bifrost-ai-gateway`,
      description: '📊 CloudWatch Dashboard URL',
    });

    new cdk.CfnOutput(this, 'AlarmTopicArn', {
      value: alarmTopic.topicArn,
      description: 'SNS topic ARN for alarm notifications',
      exportName: 'BifrostAlarmTopicArn',
    });
  }
}
