import aws_cdk as core
import aws_cdk.assertions as assertions

from devhr_project.devhr_project_stack import DevhrProjectStack

# example tests. To run these tests, uncomment this file along with the example
# resource in devhr_project/devhr_project_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = DevhrProjectStack(app, "devhr-project")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
