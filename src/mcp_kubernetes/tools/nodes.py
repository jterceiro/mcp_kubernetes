"""
Módulo para gestión de nodos de Kubernetes
Proporciona funciones para obtener información de nodos del cluster
"""

import json
from typing import Dict, Any, List
from kubernetes import client
from kubernetes.client.rest import ApiException
from config import logger, load_kube_config
from typing import Optional, Dict, Any


def get_nodes(
    context: str
) -> str:
    """
    Devuelve los nodos de un clúster Kubernetes con información detallada.

    Args:
        context: Nombre del contexto de Kubernetes a usar. Si es None, usa el contexto por defecto.

    Returns:
        str: JSON con la lista de nodos y sus detalles de capacidad y estado.

    Raises:
        ApiException: Error de la API de Kubernetes
        Exception: Error inesperado durante la operación
    """
    try:
        logger.info("Obteniendo nodos del cluster")

        # Verificar conectividad con Kubernetes
        load_kube_config(context=context)
        api = client.CoreV1Api()

        # Obtener lista de nodos
        nodes = api.list_node()
        logger.debug("Se encontraron %d nodos en el cluster", len(nodes.items))

        # Procesar información de cada nodo
        node_details = []
        for node in nodes.items:
            node_info = _extract_node_info(node)
            node_details.append(node_info)

        # Preparar respuesta
        response = {
            "total_nodes": len(node_details),
            "nodes": node_details,
            "summary": _generate_cluster_summary(node_details)
        }

        logger.info("Información de nodos obtenida exitosamente")
        return json.dumps(response, indent=2)

    except ApiException as e:
        error_msg = f"Error de API de Kubernetes al obtener nodos: {e}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
    except Exception as e:
        error_msg = f"Error inesperado al obtener nodos: {e}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})


def _extract_node_info(node) -> Dict[str, Any]:
    """
    Extrae información relevante de un nodo de Kubernetes.

    Args:
        node: Objeto nodo de Kubernetes

    Returns:
        Dict[str, Any]: Diccionario con información del nodo
    """
    # Información básica
    node_info = {
        "name": node.metadata.name,
        "labels": node.metadata.labels or {},
        "annotations": node.metadata.annotations or {},
        "creation_timestamp": node.metadata.creation_timestamp.isoformat() if node.metadata.creation_timestamp else None
    }

    # Capacidad de recursos
    capacity = node.status.capacity or {}
    allocatable = node.status.allocatable or {}

    node_info.update({
        "cpu_capacity": capacity.get("cpu", "0"),
        "memory_capacity": capacity.get("memory", "0Ki"),
        "cpu_allocatable": allocatable.get("cpu", "0"),
        "memory_allocatable": allocatable.get("memory", "0Ki"),
        "pods_capacity": capacity.get("pods", "0"),
        "storage_capacity": capacity.get("ephemeral-storage", "0Ki")
    })

    # Estado del nodo
    conditions = node.status.conditions or []
    node_info["conditions"] = _extract_node_conditions(conditions)

    # Información del sistema
    node_info.update(_extract_node_system_info(node))

    # Determinar si es master o worker
    node_info["role"] = _determine_node_role(node.metadata.labels or {})

    return node_info


def _extract_node_conditions(conditions: List) -> Dict[str, Any]:
    """
    Extrae las condiciones del estado del nodo.

    Args:
        conditions: Lista de condiciones del nodo

    Returns:
        Dict[str, Any]: Diccionario con las condiciones procesadas
    """
    processed_conditions = {}

    for condition in conditions:
        condition_type = condition.type
        processed_conditions[condition_type] = {
            "status": condition.status,
            "reason": getattr(condition, 'reason', None),
            "message": getattr(condition, 'message', None),
            "last_transition_time": condition.last_transition_time.isoformat() if condition.last_transition_time else None
        }

    return processed_conditions


def _extract_node_system_info(node) -> Dict[str, Any]:
    """
    Extrae información del sistema del nodo.

    Args:
        node: Objeto nodo de Kubernetes

    Returns:
        Dict[str, Any]: Información del sistema
    """
    node_info = node.status.node_info or {}

    return {
        "architecture": getattr(node_info, 'architecture', 'unknown'),
        "operating_system": getattr(node_info, 'operating_system', 'unknown'),
        "os_image": getattr(node_info, 'os_image', 'unknown'),
        "kernel_version": getattr(node_info, 'kernel_version', 'unknown'),
        "kubelet_version": getattr(node_info, 'kubelet_version', 'unknown'),
        "container_runtime_version": getattr(node_info, 'container_runtime_version', 'unknown')
    }


def _determine_node_role(labels: Dict[str, str]) -> str:
    """
    Determina el rol del nodo basado en sus labels.

    Args:
        labels: Labels del nodo

    Returns:
        str: Rol del nodo (master, worker, etc.)
    """
    # Buscar labels comunes para determinar el rol
    master_labels = [
        'node-role.kubernetes.io/master',
        'node-role.kubernetes.io/control-plane',
        'kubernetes.io/role=master'
    ]

    for label in master_labels:
        if label in labels:
            return "master"

    # Si tiene el label de worker
    if 'node-role.kubernetes.io/worker' in labels:
        return "worker"

    # Por defecto, asumir que es worker si no es master
    return "worker"


def _generate_cluster_summary(node_details: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Genera un resumen del cluster basado en la información de los nodos.

    Args:
        node_details: Lista con detalles de todos los nodos

    Returns:
        Dict[str, Any]: Resumen del cluster
    """
    masters = [node for node in node_details if node.get('role') == 'master']
    workers = [node for node in node_details if node.get('role') == 'worker']

    # Calcular totales de CPU y memoria
    total_cpu = sum(int(node.get('cpu_capacity', '0').replace('m', '')) for node in node_details)
    total_memory = sum(_parse_memory(node.get('memory_capacity', '0Ki')) for node in node_details)

    return {
        "master_nodes": len(masters),
        "worker_nodes": len(workers),
        "total_cpu_capacity": f"{total_cpu}m",
        "total_memory_capacity": f"{total_memory}Ki",
        "ready_nodes": len([node for node in node_details
                           if node.get('conditions', {}).get('Ready', {}).get('status') == 'True'])
    }


def _parse_memory(memory_str: str) -> int:
    """
    Convierte string de memoria a entero en Ki.

    Args:
        memory_str: String de memoria (ej: "32863720Ki")

    Returns:
        int: Memoria en Ki
    """
    try:
        if memory_str.endswith('Ki'):
            return int(memory_str[:-2])
        elif memory_str.endswith('Mi'):
            return int(memory_str[:-2]) * 1024
        elif memory_str.endswith('Gi'):
            return int(memory_str[:-2]) * 1024 * 1024
        else:
            return int(memory_str)
    except (ValueError, AttributeError):
        return 0
