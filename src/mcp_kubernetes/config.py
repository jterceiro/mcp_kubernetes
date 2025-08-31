"""
Configuración y utilidades para el servidor MCP de Kubernetes
"""

import logging
from typing import Optional
from kubernetes import client, config

# Configuración de logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Handler para consola
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Formato de logging
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def load_kube_config(
    context: Optional[str] = None
) -> None:
    """
    Carga la configuración de Kubernetes

    Args:
        context: Nombre del contexto de Kubernetes a usar. Si es None, usa el contexto por defecto.

    Raises:
        Exception: Si no se puede conectar al cluster
    """
    logger.info("Configuración cargada desde kubeconfig con contexto: %s", context)
    try:
        # Intentar cargar configuración desde el cluster (si está ejecutándose dentro)
        config.load_incluster_config()
        logger.info("Configuración cargada desde el cluster (in-cluster)")

    except config.ConfigException:
        try:
            # Cargar configuración desde kubeconfig con contexto específico
            config.load_kube_config(context=context)
            if context:
                logger.info("Configuración cargada desde kubeconfig con contexto: %s", context)
            else:
                logger.info("Configuración cargada desde kubeconfig con contexto por defecto")

        except Exception as e:
            logger.error("Error al cargar configuración de Kubernetes: %s", e)
            raise Exception(f"No se pudo conectar al cluster de Kubernetes: {e}")


def get_api_client() -> client.ApiClient:
    """
    Obtiene un cliente de API de Kubernetes

    Returns:
        client.ApiClient: Cliente de API configurado
    """
    return client.ApiClient()


def get_v1_client() -> client.CoreV1Api:
    """
    Obtiene un cliente para la API v1 de Kubernetes

    Returns:
        client.CoreV1Api: Cliente para recursos core/v1
    """
    return client.CoreV1Api()


def get_apps_v1_client() -> client.AppsV1Api:
    """
    Obtiene un cliente para la API apps/v1 de Kubernetes

    Returns:
        client.AppsV1Api: Cliente para recursos apps/v1
    """
    return client.AppsV1Api()


def test_kubernetes_connection(context: Optional[str] = None) -> bool:
    """
    Prueba la conexión con el cluster de Kubernetes

    Args:
        context: Contexto de Kubernetes a probar

    Returns:
        bool: True si la conexión es exitosa, False en caso contrario
    """
    try:
        load_kube_config(context=context)
        v1 = get_v1_client()

        # Intentar una operación simple para verificar conectividad
        nodes = v1.list_node(limit=1)
        logger.info("Conexión exitosa - Cluster tiene %d nodo(s) visible(s)", len(nodes.items))
        return True

    except Exception as e:
        logger.error("Error al probar conexión con Kubernetes: %s", e)
        return False


def get_available_contexts() -> list:
    """
    Obtiene la lista de contextos disponibles en kubeconfig

    Returns:
        list: Lista de contextos disponibles
    """
    try:
        contexts, _ = config.list_kube_config_contexts()
        return [ctx['name'] for ctx in contexts]
    except Exception as e:
        logger.error("Error al obtener contextos disponibles: %s", e)
        return []


def get_current_context() -> Optional[str]:
    """
    Obtiene el contexto actual de Kubernetes

    Returns:
        str: Nombre del contexto actual o None si no se puede determinar
    """
    try:
        _, active_context = config.list_kube_config_contexts()
        return active_context['name'] if active_context else None
    except Exception as e:
        logger.error("Error al obtener contexto actual: %s", e)
        return None


def set_default_context(context: str) -> bool:
    """
    Establece un contexto como el contexto por defecto en kubeconfig

    Args:
        context: Nombre del contexto a establecer como por defecto

    Returns:
        bool: True si se estableció correctamente, False en caso contrario
    """
    try:
        # Verificar que el contexto existe
        available_contexts = get_available_contexts()
        if context not in available_contexts:
            logger.error("El contexto '%s' no existe. Contextos disponibles: %s", context, available_contexts)
            return False

        # Usar kubectl para cambiar el contexto por defecto permanentemente
        import subprocess

        result = subprocess.run(
            ['kubectl', 'config', 'use-context', context],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            logger.info("Contexto por defecto establecido exitosamente: %s", context)

            # Verificar que el cambio fue exitoso
            new_current = get_current_context()
            if new_current == context:
                return True
            else:
                logger.error("Error al verificar cambio de contexto. Esperado: %s, Actual: %s", context, new_current)
                return False
        else:
            logger.error("Error al ejecutar kubectl use-context: %s", result.stderr)
            return False

    except Exception as e:
        logger.error("Error al establecer contexto por defecto '%s': %s", context, e)
        return False


def switch_context(context: str) -> bool:
    """
    Cambia al contexto especificado y recarga la configuración

    Args:
        context: Nombre del contexto al que cambiar

    Returns:
        bool: True si el cambio fue exitoso, False en caso contrario
    """
    try:
        # Verificar que el contexto existe
        available_contexts = get_available_contexts()
        if context not in available_contexts:
            logger.error("El contexto '%s' no existe. Contextos disponibles: %s", context, available_contexts)
            return False

        # Cargar la configuración con el nuevo contexto
        load_kube_config(context=context)

        # Verificar la conexión con el nuevo contexto
        if test_kubernetes_connection(context=context):
            logger.info("Cambio de contexto exitoso a: %s", context)
            return True
        else:
            logger.error("Error al conectar con el contexto: %s", context)
            return False

    except Exception as e:
        logger.error("Error al cambiar al contexto '%s': %s", context, e)
        return False
