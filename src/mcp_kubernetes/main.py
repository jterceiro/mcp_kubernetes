"""
Servidor MCP para gestión de Kubernetes
Proporciona herramientas para interactuar con clusters de Kubernetes
"""

import os
from typing import Optional
from mcp.server.fastmcp import FastMCP
from tools import *
from config import logger, load_kube_config, get_available_contexts, get_current_context, set_default_context

# Configuración del servidor
SERVER_NAME = os.getenv("MCP_SERVER_NAME", "Kubernetes MCP Server")
SERVER_VERSION = "1.0.0"


def initialize_mcp_server(
    context: Optional[str] = None
) -> FastMCP:
    """
    Inicializa el servidor MCP con todas las herramientas de Kubernetes

    Args:
        context: Contexto de Kubernetes a usar

    Returns:
        FastMCP: Instancia del servidor MCP configurada
    """
    try:
        logger.info("Inicializando %s v%s", SERVER_NAME, SERVER_VERSION)

        # Mostrar contextos disponibles si se especifica
        if context:
            available_contexts = get_available_contexts()
            logger.info("Contextos disponibles: %s", available_contexts)
            logger.info("Usando contexto: %s", context)
        else:
            current_context = get_current_context()
            logger.info("Usando contexto por defecto: %s", current_context)

        # Verificar conectividad con Kubernetes
        load_kube_config(context=context)
        logger.info("Conexión con Kubernetes establecida correctamente")

        # Inicializar servidor MCP
        mcp = FastMCP(SERVER_NAME)

        # Registrar herramientas con mejor organización
        register_kubernetes_tools(mcp)

        logger.info("Servidor MCP inicializado correctamente")
        return mcp

    except Exception as e:
        logger.error("Error al inicializar el servidor MCP: %s", e)
        raise


def register_kubernetes_tools(mcp: FastMCP) -> None:
    """
    Registra todas las herramientas de Kubernetes en el servidor MCP

    Args:
        mcp: Instancia del servidor MCP
    """
    tools = [
        # Herramientas de consulta
        {
            "name": "get_deployments",
            "title": "Obtener Deployments",
            "description": "Obtener el listado de deployments del cluster de kubernetes",
            "function": get_deployments
        },
        {
            "name": "get_pods",
            "title": "Obtener Pods",
            "description": "Obtener el listado de pods del cluster de kubernetes",
            "function": get_pods
        },
        {
            "name": "get_nodes",
            "title": "Listado de Nodos",
            "description": "Obtener el listado de nodos de un cluster de kubernetes con detalles de capacidad",
            "function": get_nodes
        },
        {
            "name": "get_pod_details",
            "title": "Detalles de Pod",
            "description": "Obtener información detallada de un pod específico",
            "function": get_pod_details
        },
        {
            "name": "get_logs",
            "title": "Logs de Pod",
            "description": "Obtener los logs de un pod específico en un namespace",
            "function": get_logs
        },
        {
            "name": "get_available_contexts",
            "title": "Contextos Disponibles",
            "description": "Obtener la lista de contextos disponibles en kubeconfig",
            "function": get_available_contexts
        },
        {
            "name": "get_current_context",
            "title": "Contexto Actual",
            "description": "Obtener el contexto actual de Kubernetes",
            "function": get_current_context
        },
        {
            "name": "set_default_context",
            "title": "Establecer Contexto por Defecto",
            "description": "Establecer un contexto como el contexto por defecto en kubeconfig",
            "function": set_default_context
        },
        # Herramientas de gestión
        {
            "name": "scale_deployment",
            "title": "Escalar Deployment",
            "description": "Escalar un deployment en un cluster de kubernetes",
            "function": scale_deployment
        },
        {
            "name": "rollout_deployment",
            "title": "Rollout Deployment",
            "description": "Realizar un rollout de un deployment en un cluster de kubernetes",
            "function": rollout_deployment
        }
    ]

    # Registrar cada herramienta
    for tool in tools:
        try:
            mcp.tool(
                name=tool["name"],
                title=tool["title"],
                description=tool["description"]
            )(tool["function"])
            logger.debug("Herramienta registrada: %s", tool['name'])
        except Exception as e:
            logger.error("Error al registrar herramienta %s: %s", tool['name'], e)
            raise


def main() -> None:
    """
    Función principal del servidor MCP
    """
    try:
        # Determinar contexto a usar (variable de entorno o por defecto)
        context = get_current_context()

        if context:
            logger.info("Usando contexto desde variable de entorno: %s", context)

        # Inicializar servidor con contexto específico
        mcp = initialize_mcp_server(context=context)

        # Iniciar servidor
        logger.info("Iniciando servidor MCP...")
        mcp.run()

    except KeyboardInterrupt:
        logger.info("Servidor MCP detenido por el usuario")
    except Exception as e:
        logger.error("Error crítico en el servidor MCP: %s", e)
        raise


if __name__ == "__main__":
    main()
