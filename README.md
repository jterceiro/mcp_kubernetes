# MCP Kubernetes

Model Context Protocol server for Kubernetes operations.

## Description

This project implements an MCP (Model Context Protocol) server for advanced management of Kubernetes clusters. It provides tools to query, manage, and monitor resources such as pods, deployments, nodes, and logs, with support for multiple contexts and namespaces.

## Features

- 🟢 **Pod Management:**
  - 📦 List pods by namespace and context.
  - 🔍 Retrieve complete pod details, including events, containers, volumes, and status.
- 🚀 **Deployment Management:**
  - 📦 List deployments by namespace and context.
  - 📈 Scale replicas and rollout (restart) deployments.
  - 📝 Query detailed deployment status.
- 🖥️ **Node Management:**
  - 🗂️ List nodes with capacity, status, roles, and cluster summary.
- 📄 **Pod Logs:**
  - 📝 Retrieve logs from specific pods and containers, with options for previous logs and line count.
- 🔄 **Multi-context Support:**
  - 🔎 Query and switch Kubernetes contexts.
  - ⚙️ Set default context.
- ⚙️ **Configuration and Logging:**
  - 🛠️ Utilities for loading Kubernetes configuration and structured logging.

## Installation

```sh
pip install -r requirements.txt
```

## Usage

Run the MCP server:

```sh
python src/mcp_kubernetes/main.py
```

## API Examples

The tools are exposed as MCP functions and can be invoked from compatible clients:

- **Get pods:**
  `get_pods(context="my-context", namespace="default")`
- **Pod details:**
  `get_pod_details(environment="prod", pod_name="nginx-123", namespace="default", context="my-context")`
- **Get deployments:**
  `get_deployments(context="my-context", namespace="default")`
- **Scale deployment:**
  `scale_deployment(namespace="default", deployment_name="web", replicas=5)`
- **Rollout deployment:**
  `rollout_deployment(namespace="default", deployment_name="web")`
- **Get nodes:**
  `get_nodes(context="my-context")`
- **Get logs:**
  `get_logs(context="my-context", environment="prod", pod_name="nginx-123", namespace="default", container="nginx")`
- **Available contexts:**
  `get_available_contexts()`
- **Change context:**
  `set_default_context(context="other-context")`

## Project Structure

- `src/mcp_kubernetes/main.py`: Main entry point for the MCP server.
- `src/mcp_kubernetes/config.py`: Configuration and logging utilities.
- `src/mcp_kubernetes/tools/`: Kubernetes tools modules:
  - `deployments.py`: Deployment management.
  - `pods.py`: Pod management and details.
  - `nodes.py`: Node information and summary.
  - `logs.py`: Pod log retrieval.

## Contributing

Contributions are welcome! Please open an issue or pull request for suggestions and improvements.

## License

MIT License. See the [LICENSE](LICENSE) file
