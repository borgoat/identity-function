build-WorkflowPythonPipLayer:
	python -m pip install wheel

build-WorkflowGoLayer:
	mkdir -p "${ARTIFACTS_DIR}/go"
	curl --request GET -sL \
	     --url 'https://golang.org/dl/go1.16.5.linux-amd64.tar.gz' \
	     --output - \
		 | tar -xz -C "${ARTIFACTS_DIR}/go"


