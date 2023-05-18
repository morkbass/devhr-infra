from aws_cdk import (
    Stack,
    Stage,
)
from constructs import Construct
from devhr_project_stack import DevhrProjectStack


class DevhrPipelineStage(Stage):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        devhrStack = DevhrProjectStack(self, 'DevhrStack')

        
        


        
        

        
        
        
