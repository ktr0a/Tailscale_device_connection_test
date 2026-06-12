# Legacy: Tailnet Orchestration Hub

This folder contains the original project: a hub/agent remote-command
system over Tailscale (FastAPI hub + command-executing agents + n8n).
It is **deactivated** — not used by the current chat application — but
kept intact for later development (e.g. re-adding remote command
execution or n8n automation on top of the chat nodes).

See `readme.md` and `guide.md` in this folder for the original docs.

Known issue if you revive it: `agent/agent.py` imports `requests`,
which the old docs don't list as a dependency (`pip install requests`).
