# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Web UI static files

The gns3-server and the [GNS3 Web UI](https://github.com/GNS3/gns3-web-ui/) are separate projects with separate pull requests.

- The web UI static files in `gns3server/static/web-ui/` are refreshed with the latest web-ui build only when a new version of gns3-server is released.
- Do not update or commit files under `gns3server/static/web-ui/` in regular pull requests.
- If a server change also needs a web UI change, submit a separate pull request in the gns3-web-ui repository.
