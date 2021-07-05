import base64
import io
import os
import tarfile
import tempfile
import zipfile

from enum import Enum

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.event_handler.api_gateway import ApiGatewayResolver
from aws_lambda_powertools.utilities.parser import envelopes, parse, BaseModel

from aws_lambda_builders.builder import LambdaBuilder

# https://awslabs.github.io/aws-lambda-powertools-python/#features
tracer = Tracer()
logger = Logger()
metrics = Metrics()
app = ApiGatewayResolver()

# Global variables are reused across execution contexts (if available)
session = boto3.Session()


class LanguageEnum(str, Enum):
    python = 'python'
    go = 'go'


class DependencyManagerEnum(str, Enum):
    pip = 'pip'
    modules = 'modules'


class BuildModel(BaseModel):
    archive: str  #: Base64 encoded Tar archive - containing the source code
    language: LanguageEnum
    dependencyManager: DependencyManagerEnum


@app.post('/build')
def build():
    request: BuildModel = parse(event=app.current_event.raw_event,
                                model=BuildModel,
                                envelope=envelopes.ApiGatewayEnvelope)

    with tempfile.TemporaryDirectory() as td:
        dir_source = os.path.join(td, 'src')
        dir_artifacts = os.path.join(td, 'artifacts')
        dir_scratch = os.path.join(td, 'scratch')

        archive_raw = base64.b64decode(request.archive, validate=True)
        archive_buf = io.BytesIO(archive_raw)
        tar = tarfile.open(fileobj=archive_buf, mode='r:*')
        tar.extractall(path=dir_source)
        lb = LambdaBuilder(
            language=request.language,
            dependency_manager=request.dependencyManager,
            application_framework=None,
        )
        res = lb.build(  # TODO Get parameters from event
            source_dir=dir_source,
            artifacts_dir=dir_artifacts,
            scratch_dir=dir_scratch,
            manifest_path='go.mod',
            runtime='go1.x',
            executable_search_paths=['/opt/go/bin'],
            options={
                'artifact_executable_name': 'my-handler',
            },
        )
        logger.debug(res)
        out_buf = io.BytesIO()
        out_zip = zipfile.ZipFile(out_buf, 'x')
        for root, dirs, files in os.walk(dir_artifacts):
            for file in files:
                out_zip.write(os.path.join(root, file),
                              os.path.relpath(os.path.join(root, file), dir_artifacts))
        return {'lambda_archive': base64.b64encode(out_buf.getvalue()).decode()}


@app.get("/hello")
def hello():
    query_string_name = app.current_event.get_query_string_value(name="name", default_value="universe")
    return {"message": f"hello {query_string_name}"}


@app.get("/hello/<name>")
def hello_you(name):
    # query_strings_as_dict = app.current_event.query_string_parameters
    # json_payload = app.current_event.json_body
    return {"message": f"hello {name}"}


@metrics.log_metrics(capture_cold_start_metric=True)
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    try:
        return app.resolve(event, context)
    except Exception as e:
        logger.exception(e)
        raise
