from aws_cdk import (
    Stack,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    aws_codebuild as codebuild,
    SecretValue,
    #StackProps,
    Duration,
    CfnOutput,
    pipelines,
    aws_ssm as ssm
)
from constructs import Construct

from devhr_project.pipeline_stage import DevhrPipelineStage


class DevhrBackendPipelineStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        
        #github_branch = ssm.StringParameter.from_string_parameter_attributes(self, "github_branch",parameter_name="devhour-backend-github-branch").string_value,
        
        pipeline = pipelines.CodePipeline(self, "Pipeline",
            #pipeline_name="devhr",
            synth=pipelines.ShellStep("Synth",
                input = pipelines.CodePipelineSource.connection('morkbass/devhr-infra', 'master',
                    connection_arn='arn:aws:codestar-connections:us-east-1:075341441208:connection/8f80c0a9-39ff-4f30-be7b-4b57addce22d'),
                commands=[
                    "ls -ll && pwd",
                    "npm install -g aws-cdk",  # Installs the cdk cli on Codebuild
                    "pip install -r requirements.txt",  # Instructs Codebuild to install required packages
                    "npx cdk synth",
                ]
            ),
            cross_account_keys=False,
        )
        
        devStage = pipeline.add_stage(DevhrPipelineStage(self, "dev"))
         
        devStage.add_post(pipelines.ManualApprovalStep('approval'))
        
        
