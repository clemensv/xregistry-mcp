#!/bin/bash
# run on Linux

# Start xregistry server in background
CONTAINER_NAME="xregistry-server"
# Check if the container is already running
if [ "$(docker ps -q -f name=^/${CONTAINER_NAME}$)" ]; then
  echo "Container ${CONTAINER_NAME} is already running."
  CONTAINER_ID=$(docker ps -q -f name=^/${CONTAINER_NAME}$)
else
  CONTAINER_ID=$(docker run -d --name "${CONTAINER_NAME}" -p 8080:8080 ghcr.io/xregistry/xrserver-all --recreatedb)
fi

# Wait until xregistry server responds with HTTP 200, with a timeout
ATTEMPTS=0
MAX_ATTEMPTS=60
until curl --silent --get http://localhost:8080 -i | grep "200 OK" > /dev/null; do
  echo "Waiting for xregistry server..."
  sleep 5
  ATTEMPTS=$((ATTEMPTS+1))
  if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
    echo "xregistry server did not respond after $MAX_ATTEMPTS seconds."
    exit 1
  fi
done

# Determine repository root directory
SCRIPT_DIR=$(dirname "$(realpath "$0")")
REPO_ROOT=$(realpath "$SCRIPT_DIR/..")

# Update model using the xr docker container
docker run --rm --network host -v "$REPO_ROOT":/workspace ghcr.io/xregistry/xr model update /workspace/xreg/model.json -s localhost:8080

# Dynamically create entries for each registry index.json (using ../registry)
REGISTRY_DIR="$REPO_ROOT/registry"
find "$REGISTRY_DIR" -type f -name index.json | while read file; do
  # Get relative path from registry directory and remove the trailing /index.json
  path=${file#"$REGISTRY_DIR"/}
  path=${path%/index.json}
  # Run the xr create command inside the container; note that the JSON file is referenced via /workspace
  docker run --rm --network host -v "$REPO_ROOT":/workspace ghcr.io/xregistry/xr create "$path" -d "@/workspace/registry/$path/index.json" -s localhost:8080
  if [ $? -ne 0 ]; then
    echo "Error processing file: $file"
  else
    echo "Processed file: $file"
  fi
done

mkdir -p $REPO_ROOT/live
# Download entire live directory using the xr docker container
docker run --rm --network host -v "$REPO_ROOT":/workspace ghcr.io/xregistry/xr download -s localhost:8080 $REPO_ROOT/live -u https://clemensv.github.io/xregistry-mcp/

docker stop "${CONTAINER_ID}"
docker rm "${CONTAINER_ID}"

python "$REPO_ROOT/index/build_index.py"
cp $REPO_ROOT/index/flex/*.flex.json $REPO_ROOT/live

cp $REPO_ROOT/xreg/staticwebapp.conmfig.json $REPO_ROOT/live/staticwebapp.config.json

echo "xregistry server stopped and removed."