# run on Linux

if [ ! -d "xregistry-server" ]; then
    git clone https://github.com/xregistry/server xregistry-server
fi
cd xregistry-server
make cmds
cd ../

cd ..

docker run -ti -p 8080:8080 ghcr.io/xregistry/xrserver-all --recreatedb
sleep 30
xregistry-server/xr model update xreg/model.json -s localhost:8080

xregistry-server/xr create mcpproviders/google/servers/maps -d @registry/mcpproviders/google/servers/maps/index.json -s localhost:8080
xregistry-server/xr download -s localhost:8080 live -u https://clemensv.github.io/xregistry-mcp/