from aws_cdk import (
    # Duration,
    Stack,
    # aws_sqs as sqs,
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment,
    aws_s3_notifications as s3n,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_event_sources,
    aws_iam as iam,
    aws_apigateway as apigateway,
    aws_cognito as cognito,
    aws_sqs as sqs,
    RemovalPolicy,
    Duration,
    CfnOutput
)
from constructs import Construct
import json


class DevhrProjectStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here

        # example resource
        # queue = sqs.Queue(
        #     self, "DevhrProjectQueue",
        #     visibility_timeout=Duration.seconds(300),
        # )
        imageBucket = s3.Bucket(self, "cdk-rekn-imagebucket", bucket_name="image-bucket-scj",versioned=True,removal_policy=RemovalPolicy.DESTROY)
        
        imageBucket.add_cors_rule(
            allowed_methods=[s3.HttpMethods.GET,s3.HttpMethods.PUT],
            allowed_origins=["*"],
            # the properties below are optional
            allowed_headers=["*"],
            max_age=3000
        )
        
        
        #auto_delete_objects
        resizedBucketName = imageBucket.bucket_name + "-resized"
        resizedBucket = s3.Bucket(self, "cdk-rekn-imagebucket-resized", bucket_name=resizedBucketName,versioned=True,removal_policy=RemovalPolicy.DESTROY)

        resizedBucket.add_cors_rule(
            allowed_methods=[s3.HttpMethods.GET,s3.HttpMethods.PUT],
            allowed_origins=["*"],
            # the properties below are optional
            allowed_headers=["*"],
            max_age=3000
        )
        
        dynamoTable = dynamodb.Table(self, "Table",table_name="imageLabels",
            partition_key=dynamodb.Attribute(name="image", type=dynamodb.AttributeType.STRING))
        
        rekLayer= lambda_.LayerVersion(self, "pil",
            code=lambda_.Code.from_asset(path="reklayer"),
            compatible_runtimes = [lambda_.Runtime.PYTHON_3_7],
            description= 'A layer to enable the PIL library in our rekongnition Lambda')           
        
        rekFn= lambda_.Function(self, "rekFn",
            code=lambda_.Code.from_asset(path= "rekognitionlambda"),
            runtime=lambda_.Runtime.PYTHON_3_7,
            handler="index.handler",
            timeout= Duration.seconds(30),
            memory_size=1024,
            layers = [rekLayer],
            environment= {"TABLE": dynamoTable.table_name,"BUCKET": imageBucket.bucket_name, "THUMBBUCKET": resizedBucket.bucket_name}            
            )
        
        # rekFn.add_event_source(lambda_event_sources.S3EventSource(bucket=imageBucket,
        #     events=[s3.EventType.OBJECT_CREATED_PUT]))
        imageBucket.grant_read(rekFn)
        resizedBucket.grant_put(rekFn)
        dynamoTable.grant_read_write_data(rekFn)
        rekFn.add_to_role_policy (iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions= ['rekognition:DetectLabels'],
            resources=['*']
            )
        )
        
        serviceFn= lambda_.Function(self, "rekservice",
            code=lambda_.Code.from_asset(path= "servicelambda"),
            runtime=lambda_.Runtime.PYTHON_3_7,
            handler="index.handler",
            timeout= Duration.seconds(30),
            memory_size=1024,
            environment= {"TABLE": dynamoTable.table_name,"BUCKET": imageBucket.bucket_name, "RESIZEDBUCKET": resizedBucket.bucket_name}            
        ) 
        
        imageBucket.grant_write(serviceFn)
        resizedBucket.grant_write(serviceFn)
        dynamoTable.grant_read_write_data(serviceFn)
        
        api = apigateway.LambdaRestApi(self, "imageAPI",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS
            ),
            handler=serviceFn,
            proxy=False
        )
        
        lambdaIntegration = apigateway.LambdaIntegration(serviceFn,
            proxy=False,
            request_parameters={
                "integration.request.querystring.action": "method.request.querystring.action",
                "integration.request.querystring.key": "method.request.querystring.key"                        
            },
            #request_templates={"application/json": { "statusCode": 200 }},
            request_templates={
                #'application/json': '{"action": "$util.escapeJavaScript($input.params(\'action\'))", "key": "$util.escapeJavaScript($input.params(\'key\'))"}'
                'application/json': json.dumps({'action': f"$util.escapeJavaScript($input.params('action'))",
                'key': f"$util.escapeJavaScript($input.params('key'))"})
            },
            passthrough_behavior=apigateway.PassthroughBehavior.WHEN_NO_TEMPLATES,
            integration_responses=[
                apigateway.IntegrationResponse(status_code='200',response_parameters={"method.response.header.Access-Control-Allow-Origin": "'*'"}),
                apigateway.IntegrationResponse(status_code='500',selection_pattern='.*',response_parameters={"method.response.header.Access-Control-Allow-Origin": "'*'"})
            ]
        )
        
        userPool = cognito.UserPool(self, "UserPool", 
            self_sign_up_enabled=True,
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            sign_in_aliases=cognito.SignInAliases(username=True, email=True)
        )
        
        userPoolClient = userPool.add_client("UserPoolClient",generate_secret=False)
        
        identityPool = cognito.CfnIdentityPool(self, "ImageRekognitionIdentityPool",
            allow_unauthenticated_identities=False,
            cognito_identity_providers=[ 
                cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                    client_id=userPoolClient.user_pool_client_id,
                    provider_name=userPool.user_pool_provider_name)
            ]
        )        
        
        # auth = apigateway.CfnAuthorizer(self, "MyCfnAuthorizer",
        #     name="customer-authorizer",
        #     identity_source= "method.request.header.Authorization",
        #     provider_arns=[userPool.user_pool_arn],
        #     rest_api_id = api.rest_api_id,
        #     type = "COGNITO_USER_POOLS"
        # )
        auth = apigateway.CognitoUserPoolsAuthorizer(self, "Authorizer",
            cognito_user_pools=[userPool],
            authorizer_name="cognito-authorizer",
            identity_source="method.request.header.Authorization",
        )        
        
        authenticatedRole = iam.Role(self, "ImageRekognitionAuthenticatedRole",
            assumed_by=iam.FederatedPrincipal("cognito-identity.amazonaws.com", 
                {
                "StringEquals": {"cognito-identity.amazonaws.com:aud": identityPool.ref},
                "ForAnyValue:StringLike": {"cognito-identity.amazonaws.com:amr": "authenticated"}
                },
                "sts:AssumeRoleWithWebIdentity"
            )
        )
        
        authenticatedRole.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["s3:GetObject","s3:PutObject"],
            resources=[
                imageBucket.bucket_arn + "/private${cognito-identity.amazonaws.com:sub}/*",
                imageBucket.bucket_arn + "/private${cognito-identity.amazonaws.com:sub}",
                resizedBucket.bucket_arn + "/private${cognito-identity.amazonaws.com:sub}/*",
                resizedBucket.bucket_arn + "/private${cognito-identity.amazonaws.com:sub}"
                ]
            )
        )

        authenticatedRole.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["s3:ListBucket"],
            resources=[
                imageBucket.bucket_arn,
                resizedBucket.bucket_arn
            ],
            conditions= {
                "StringLike": {"s3:prefix": ["private/${cognito-identity.amazonaws.com:sub}/*"]}
            }
            )
        )        
        
        cfn_identity_pool_role_attachment = cognito.CfnIdentityPoolRoleAttachment(self, "MyCfnIdentityPoolRoleAttachment",
            identity_pool_id=identityPool.ref,
            roles = { "authenticated": authenticatedRole.role_arn}
        )        

    ## =====================================================================================
    ## API Gateway
    ## =====================================================================================
        image_api = api.root.add_resource('images')
        # GET /images
        image_api.add_method('GET', lambdaIntegration, 
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer= auth,
            request_parameters={
                'method.request.querystring.action': True,
                'method.request.querystring.key': True
            },
            method_responses=[
                apigateway.MethodResponse(
                    status_code='200',
                    response_parameters={
                         "method.response.header.Access-Control-Allow-Origin": True,
                    },
                ),
                apigateway.MethodResponse(
                    status_code='500',
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                )
            ]
        )
        # DELETE /images
        image_api.add_method('DELETE', lambdaIntegration,
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer= auth,
            request_parameters={
                'method.request.querystring.action': True,
                'method.request.querystring.key': True
            },
            method_responses=[
                apigateway.MethodResponse(
                    status_code='200',
                    response_parameters={
                        'method.response.header.Access-Control-Allow-Origin': True,
                    },
                ),
                apigateway.MethodResponse(
                    status_code='500',
                    response_parameters={
                        'method.response.header.Access-Control-Allow-Origin': True,
                    },
                )
            ]
        )
        
        webBucket = s3.Bucket(self, "web-site-bucket", bucket_name="website-bucket-scj",
            website_index_document="index.html",
            website_error_document="index.html",
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL
            # public_read_access=True,
        )
        
        webBucket.add_to_resource_policy(iam.PolicyStatement(
            actions=["s3:GetObject"],
            resources=[webBucket.bucket_arn + "/*"],
            principals=[iam.AnyPrincipal()],
            conditions= {
                "IpAddress": {"aws:SourceIp": ["201.245.213.104"]},
                }
            )
        )
        
            
        ## ===========================================================================
        ## Deploy site contents to S3 bucket
        ## ===========================================================================

        s3_deployment.BucketDeployment(self, "deploy-website",
            sources=[s3_deployment.Source.asset("./public")],
            destination_bucket=webBucket
        )

        ## ===========================================================================
        ## SQS
        ## ===========================================================================
        
        dlQueue = sqs.Queue(self, "ImageDLQueue",
            queue_name="ImageDLQueue"
        )        
        
        queue = sqs.Queue(self, "ImageQueue",
            queue_name="ImageQueue",        
            visibility_timeout=Duration.seconds(30),
            receive_message_wait_time=Duration.seconds(20),
            dead_letter_queue={
                "max_receive_count": 2,
                "queue": dlQueue
            }
        )
        
        imageBucket.add_object_created_notification(s3n.SqsDestination(queue), s3.NotificationKeyFilter(prefix="private/"))
        
        rekFn.add_event_source(lambda_event_sources.SqsEventSource(queue))
        
        
    ## =====================================================================================
    ## Lambda(Rekognition) to consume messages from SQS
    ## =====================================================================================
    
    


        CfnOutput(self, "imageBucketOutput", value=imageBucket.bucket_name)
        CfnOutput(self, "dynamoTable", value=dynamoTable.table_name)
        CfnOutput(self, "imageBucketResizedOutput", value=resizedBucket.bucket_name)
        CfnOutput(self, "UserPoolId", value=userPool.user_pool_id )
        CfnOutput(self, "AppClientId", value=userPoolClient.user_pool_client_id)
        CfnOutput(self, "identityPoolID", value=identityPool.ref)
        CfnOutput(self, "webSiteOutput", value=webBucket.bucket_website_url)