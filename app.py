#!/usr/bin/env python3
import os

import aws_cdk as cdk

from devhr_project.devhr_project_stack import DevhrProjectStack
from devhr_project.devhr_backend_pipeline_stack import DevhrBackendPipelineStack

app = cdk.App()
DevhrProjectStack(app, "DevhrProjectStack")
DevhrBackendPipelineStack(app, "DevhrBackendPipelineStack")


app.synth()
