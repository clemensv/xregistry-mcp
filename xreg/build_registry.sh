#!/bin/bash
# run on Linux

CONTAINER_NAME="xregistry-server"
ARCHIVE_PATH="/tmp/xr_live_data.tar.gz"

# Determine repository root directory
SCRIPT_DIR=$(dirname "$(realpath "$0")")
REPO_ROOT=$(realpath "$SCRIPT_DIR/..")
DATA_EXPORT_DIR="$REPO_ROOT/live"

# Start or reuse the xregistry server container
if [ "$(docker ps -q -f name="${CONTAINER_NAME}")" ]; then
  echo "Container ${CONTAINER_NAME} is already running."
  CONTAINER_ID=$(docker ps -q -f name="${CONTAINER_NAME}")
else
  CONTAINER_ID=$(docker run -d --name "${CONTAINER_NAME}" -v "$REPO_ROOT":/workspace -p 8080:8080 ghcr.io/xregistry/xrserver-all --recreatedb)
fi

# Wait for the server to be ready
echo "Waiting for xregistry server to be ready..."
until curl --silent --get http://localhost:8080 -i | grep "200 OK" > /dev/null; do
  sleep 5
done

# Update the model
echo "Updating model..."
docker exec "${CONTAINER_ID}" /xr model update /workspace/xreg/model.json -s localhost:8080

# Create entries for each registry index.json
echo "Creating registry entries..."
docker exec "${CONTAINER_ID}" /bin/sh -c '
 REGISTRY_DIR=/workspace/registry
 find $REGISTRY_DIR -type f -name index.json | while read file; do
   path=${file#"$REGISTRY_DIR"/}
   path=${path%/index.json}
   /xr create "$path" -d "@$file" -s localhost:8080
   if [ $? -ne 0 ]; then
     echo "Error processing file: $file"
   else
     echo "Processed file: $file"
   fi 
 done
'

# Export the live data as a tarball
echo "Exporting live data to $ARCHIVE_PATH..."
docker exec "${CONTAINER_ID}" /bin/sh -c "
  mkdir -p /tmp/live
  /xr download -s localhost:8080 /tmp/live -u https://mcpxreg.org/
  cd /tmp/live
  tar czf $ARCHIVE_PATH .
"

# Copy the archive to the host
echo "Copying archive to $DATA_EXPORT_DIR..."
mkdir -p "$DATA_EXPORT_DIR"
docker cp "${CONTAINER_ID}:$ARCHIVE_PATH" "$DATA_EXPORT_DIR/xr_live_data.tar.gz"
tar xzf "$DATA_EXPORT_DIR/xr_live_data.tar.gz" -C "$DATA_EXPORT_DIR"
rm "$DATA_EXPORT_DIR/xr_live_data.tar.gz"

# Stop and remove the container
echo "Stopping and removing xregistry server..."
docker stop "${CONTAINER_ID}"
docker rm "${CONTAINER_ID}"

# Build the index
echo "Building index..."
yes | pip install pandas --quiet
python "$REPO_ROOT/index/build_index.py"

# Copy additional files
echo "Copying flex.json files to $REPO_ROOT/live..."
cp "$REPO_ROOT/index/flex/"*.flex.json "$REPO_ROOT/live"
cp "$REPO_ROOT/xreg/registry-staticwebapp.config.json" "$REPO_ROOT/live/staticwebapp.config.json"

echo "xregistry server stopped and removed."
echo "Process complete."
