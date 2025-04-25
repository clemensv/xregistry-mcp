# run on Linux

# if [ ! -d "xregistry-server" ]; then
#     git clone https://github.com/xregistry/server xregistry-server
# fi
# cd xregistry-server
# make cmds
# cd ..

# # Start xregistry server in background
# docker run -d -p 8080:8080 ghcr.io/xregistry/xrserver-all --recreatedb

# # Wait until xregistry server responds with HTTP 200
# until curl --silent --head --fail http://localhost:8080 >/dev/null; do
#   echo "Waiting for xregistry server..."
#   sleep 1
# done

# Update model
../xregistry-server/xr model update xreg/model.json -s localhost:8080

# Dynamically create entries for each registry index.json
find registry -type f -name index.json | while read file; do
  path=${file#registry/}
  path=${path%/index.json}
  ../xregistry-server/xr create "$path" -d "@$file" -s localhost:8080
done

# Download entire live directory
../xregistry-server/xr download -s localhost:8080 live -u https://clemensv.github.io/xregistry-mcp/