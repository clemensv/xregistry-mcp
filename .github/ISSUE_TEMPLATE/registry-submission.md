---
name: Registry submission
about: File this issue when you want to add a new MCP Server to the registry
title: ''
labels: ''
assignees: ''

---

Fill out the following yaml:

~~~
repo: <repo>
path: <path>
branch: <branch>
mcpprovider: <the mcp provider group in the registry>
server: <the server name in the registry>
~~~

whereby:
- **repo**: the path to the repo (e.g. org/repo) on Github or a full URL to a repo elsewhere
- **path**: the path in the repo where the `mcp.json` file can be found
- **branch**: the branch of the repo to look up
- **mcpprovider**: the name of the mcpprovider group to put the registration into
- **server**: the name of the server to register
