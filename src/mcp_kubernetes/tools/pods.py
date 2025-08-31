"""
Módulo para gestión de pods de Kubernetes
Proporciona funciones para obtener información básica y detallada de pods
"""

import json
from typing import Dict, Any, List, Optional
from kubernetes import client
from kubernetes.client.rest import ApiException
from config import logger, load_kube_config
from typing import Optional, Dict, Any


def get_pods(
    context: str,
    namespace: str
) -> str:
    """
    Devuelve los pods de un clúster Kubernetes.

    Args:
        context: Nombre del contexto de Kubernetes a usar. Si es None, usa el contexto por defecto.
        namespace (str): Namespace específico para filtrar los pods.
                        Si es None o vacío, devuelve de todos los namespaces.

    Returns:
        str: JSON con el listado de pods y sus detalles básicos.

    Raises:
        ApiException: Error de la API de Kubernetes
        Exception: Error inesperado durante la operación
    """
    try:
        logger.info("Obteniendo pods del namespace: %s", namespace or 'todos')

        load_kube_config(context=context)
        api = client.CoreV1Api()

        # Obtener pods con timeout
        if namespace and namespace.strip():
            pods = api.list_namespaced_pod(namespace, _request_timeout=30)
        else:
            pods = api.list_pod_for_all_namespaces(_request_timeout=30)

        pod_list = []
        for pod in pods.items:
            pod_info = _extract_basic_pod_info(pod)
            pod_list.append(pod_info)

        # Generar estadísticas
        stats = _generate_pod_statistics(pod_list)

        response = {
            "total_pods": len(pod_list),
            "namespace": namespace or "all",
            "statistics": stats,
            "pods": pod_list
        }

        logger.info("Se obtuvieron %d pods exitosamente", len(pod_list))
        return json.dumps(response, indent=2)

    except ApiException as e:
        error_msg = f"Error de API de Kubernetes al obtener pods: {e}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg, "namespace": namespace})
    except Exception as e:
        error_msg = f"Error inesperado al obtener pods: {e}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg, "namespace": namespace})


def get_pod_details(
    environment: str,
    pod_name: str,
    namespace: str,
    context: str) -> str:
    """
    Devuelve información detallada de un pod específico.

    Args:
        environment (str): Entorno (para compatibilidad con otros métodos)
        pod_name (str): Nombre del pod
        namespace (str): Namespace donde está el pod
        context (str): Contexto de Kubernetes a usar

    Returns:
        str: JSON con información detallada del pod

    Raises:
        ApiException: Error de la API de Kubernetes
        Exception: Error inesperado durante la operación
    """
    try:
        # Validar parámetros
        if not all([pod_name, namespace]):
            raise ValueError("pod_name y namespace son requeridos")

        logger.info("Obteniendo detalles del pod %s en namespace %s (env: %s)", pod_name, namespace, environment)

        load_kube_config(context=context)
        api = client.CoreV1Api()

        # Obtener información del pod con timeout
        pod = api.read_namespaced_pod(name=pod_name, namespace=namespace, _request_timeout=30)

        # Obtener eventos relacionados con el pod
        events = api.list_namespaced_event(
            namespace=namespace,
            field_selector=f"involvedObject.name={pod_name}",
            _request_timeout=30
        )

        # Preparar información detallada
        pod_details = _build_detailed_pod_info(pod, events.items, environment)

        logger.info("Detalles del pod %s obtenidos exitosamente", pod_name)
        return json.dumps(pod_details, indent=2)

    except ApiException as e:
        error_msg = _handle_api_exception(e, pod_name, namespace)
        logger.error(error_msg)
        return json.dumps({"error": error_msg, "pod_name": pod_name, "namespace": namespace})
    except ValueError as e:
        error_msg = f"Error de validación: {e}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})
    except Exception as e:
        error_msg = f"Error inesperado al obtener detalles del pod: {e}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg, "pod_name": pod_name, "namespace": namespace})


def _extract_basic_pod_info(pod) -> Dict[str, Any]:
    """
    Extrae información básica de un pod.

    Args:
        pod: Objeto pod de Kubernetes

    Returns:
        Dict[str, Any]: Información básica del pod
    """
    # Determinar si el pod está ready
    ready = _is_pod_ready(pod)

    # Calcular reinicio total
    restart_count = _calculate_total_restarts(pod)

    # Calcular edad del pod
    age = _calculate_pod_age(pod)

    return {
        "name": pod.metadata.name,
        "namespace": pod.metadata.namespace,
        "status": pod.status.phase,
        "ready": ready,
        "ready_containers": _get_ready_containers_count(pod),
        "total_containers": len(pod.spec.containers) if pod.spec.containers else 0,
        "restart_count": restart_count,
        "node_name": pod.spec.node_name,
        "pod_ip": pod.status.pod_ip,
        "age": age,
        "labels": pod.metadata.labels or {},
        "creation_timestamp": pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else None
    }


def _is_pod_ready(pod) -> bool:
    """Determina si el pod está en estado Ready"""
    if not pod.status.conditions:
        return False

    for condition in pod.status.conditions:
        if condition.type == "Ready" and condition.status == "True":
            return True
    return False


def _calculate_total_restarts(pod) -> int:
    """Calcula el número total de reinicios de todos los contenedores"""
    if not pod.status.container_statuses:
        return 0

    return sum(
        container_status.restart_count or 0
        for container_status in pod.status.container_statuses
    )


def _get_ready_containers_count(pod) -> str:
    """Obtiene el conteo de contenedores ready vs total"""
    if not pod.status.container_statuses:
        total = len(pod.spec.containers) if pod.spec.containers else 0
        return f"0/{total}"

    ready_count = sum(
        1 for container_status in pod.status.container_statuses
        if container_status.ready
    )
    total_count = len(pod.status.container_statuses)
    return f"{ready_count}/{total_count}"


def _calculate_pod_age(pod) -> Optional[str]:
    """Calcula la edad del pod desde su creación"""
    if not pod.metadata.creation_timestamp:
        return None

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    created = pod.metadata.creation_timestamp.replace(tzinfo=timezone.utc)
    age = now - created

    days = age.days
    hours, remainder = divmod(age.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    if days > 0:
        return f"{days}d{hours}h"
    elif hours > 0:
        return f"{hours}h{minutes}m"
    else:
        return f"{minutes}m"


def _generate_pod_statistics(pod_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Genera estadísticas de los pods.

    Args:
        pod_list: Lista de pods

    Returns:
        Dict[str, Any]: Estadísticas agregadas
    """
    if not pod_list:
        return {}

    status_counts = {}
    total_restarts = 0
    ready_pods = 0

    for pod in pod_list:
        # Contar por status
        status = pod.get("status", "Unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

        # Sumar reinicios
        total_restarts += pod.get("restart_count", 0)

        # Contar pods ready
        if pod.get("ready", False):
            ready_pods += 1

    return {
        "by_status": status_counts,
        "ready_pods": ready_pods,
        "total_restarts": total_restarts,
        "ready_percentage": round((ready_pods / len(pod_list)) * 100, 2) if pod_list else 0
    }


def _build_detailed_pod_info(pod, events: List, environment: str) -> Dict[str, Any]:
    """
    Construye información detallada del pod.

    Args:
        pod: Objeto pod de Kubernetes
        events: Lista de eventos del pod
        environment: Entorno del pod

    Returns:
        Dict[str, Any]: Información detallada del pod
    """
    pod_details = {
        "environment": environment,
        "metadata": _extract_pod_metadata(pod),
        "spec": _extract_pod_spec(pod),
        "status": _extract_pod_status(pod),
        "events": _extract_pod_events(events)
    }

    return pod_details


def _extract_pod_metadata(pod) -> Dict[str, Any]:
    """Extrae metadatos del pod"""
    metadata = {
        "name": pod.metadata.name,
        "namespace": pod.metadata.namespace,
        "creation_timestamp": pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else None,
        "labels": pod.metadata.labels or {},
        "annotations": pod.metadata.annotations or {},
        "owner_references": []
    }

    # Owner references
    if pod.metadata.owner_references:
        for owner_ref in pod.metadata.owner_references:
            metadata["owner_references"].append({
                "kind": owner_ref.kind,
                "name": owner_ref.name,
                "uid": owner_ref.uid,
                "controller": getattr(owner_ref, 'controller', False)
            })

    return metadata


def _extract_pod_spec(pod) -> Dict[str, Any]:
    """Extrae especificaciones del pod"""
    spec = {
        "node_name": pod.spec.node_name,
        "restart_policy": pod.spec.restart_policy,
        "service_account": getattr(pod.spec, 'service_account', None),
        "service_account_name": getattr(pod.spec, 'service_account_name', None),
        "security_context": _extract_security_context(pod.spec.security_context),
        "containers": [],
        "init_containers": [],
        "volumes": []
    }

    # Contenedores principales
    if pod.spec.containers:
        for container in pod.spec.containers:
            spec["containers"].append(_extract_container_info(container))

    # Init containers
    if getattr(pod.spec, 'init_containers', None):
        for container in pod.spec.init_containers:
            spec["init_containers"].append(_extract_container_info(container))

    # Volúmenes
    if pod.spec.volumes:
        for volume in pod.spec.volumes:
            spec["volumes"].append(_extract_volume_info(volume))

    return spec


def _extract_container_info(container) -> Dict[str, Any]:
    """Extrae información de un contenedor"""
    container_info = {
        "name": container.name,
        "image": container.image,
        "command": container.command,
        "args": container.args,
        "working_dir": getattr(container, 'working_dir', None),
        "ports": [],
        "env": [],
        "volume_mounts": [],
        "resources": {},
        "security_context": {},
        "liveness_probe": None,
        "readiness_probe": None
    }

    # Puertos
    if container.ports:
        for port in container.ports:
            container_info["ports"].append({
                "name": getattr(port, 'name', None),
                "container_port": port.container_port,
                "protocol": getattr(port, 'protocol', 'TCP'),
                "host_port": getattr(port, 'host_port', None)
            })

    # Variables de entorno
    if container.env:
        for env_var in container.env:
            env_info = {"name": env_var.name}

            if env_var.value is not None:
                env_info["value"] = env_var.value
            elif env_var.value_from:
                env_info["value_from"] = _extract_env_value_from(env_var.value_from)

            container_info["env"].append(env_info)

    # Volume mounts
    if container.volume_mounts:
        for vm in container.volume_mounts:
            container_info["volume_mounts"].append({
                "name": vm.name,
                "mount_path": vm.mount_path,
                "read_only": getattr(vm, 'read_only', False),
                "sub_path": getattr(vm, 'sub_path', None)
            })

    # Resources
    if container.resources:
        if container.resources.requests:
            container_info["resources"]["requests"] = dict(container.resources.requests)
        if container.resources.limits:
            container_info["resources"]["limits"] = dict(container.resources.limits)

    # Security context
    container_info["security_context"] = _extract_security_context(container.security_context)

    # Probes
    if getattr(container, 'liveness_probe', None):
        container_info["liveness_probe"] = _extract_probe_info(container.liveness_probe)

    if getattr(container, 'readiness_probe', None):
        container_info["readiness_probe"] = _extract_probe_info(container.readiness_probe)

    return container_info


def _extract_env_value_from(value_from) -> Dict[str, Any]:
    """Extrae información de valueFrom de variables de entorno"""
    if value_from.config_map_key_ref:
        return {
            "type": "configMapKeyRef",
            "name": value_from.config_map_key_ref.name,
            "key": value_from.config_map_key_ref.key
        }
    elif value_from.secret_key_ref:
        return {
            "type": "secretKeyRef",
            "name": value_from.secret_key_ref.name,
            "key": value_from.secret_key_ref.key
        }
    elif value_from.field_ref:
        return {
            "type": "fieldRef",
            "field_path": value_from.field_ref.field_path
        }
    elif value_from.resource_field_ref:
        return {
            "type": "resourceFieldRef",
            "resource": value_from.resource_field_ref.resource
        }
    else:
        return {"type": "unknown"}


def _extract_security_context(security_context) -> Dict[str, Any]:
    """Extrae contexto de seguridad"""
    if not security_context:
        return {}

    context = {}

    # Campos comunes
    for field in ['run_as_user', 'run_as_group', 'run_as_non_root', 'fs_group']:
        if hasattr(security_context, field):
            value = getattr(security_context, field)
            if value is not None:
                context[field] = value

    # Campos específicos de contenedor
    for field in ['read_only_root_filesystem', 'allow_privilege_escalation']:
        if hasattr(security_context, field):
            value = getattr(security_context, field)
            if value is not None:
                context[field] = value

    # Capabilities (solo para contenedores)
    if hasattr(security_context, 'capabilities') and security_context.capabilities:
        context["capabilities"] = {
            "add": getattr(security_context.capabilities, 'add', []),
            "drop": getattr(security_context.capabilities, 'drop', [])
        }

    return context


def _extract_probe_info(probe) -> Dict[str, Any]:
    """Extrae información de probes"""
    probe_info = {
        "initial_delay_seconds": getattr(probe, 'initial_delay_seconds', 0),
        "period_seconds": getattr(probe, 'period_seconds', 10),
        "timeout_seconds": getattr(probe, 'timeout_seconds', 1),
        "failure_threshold": getattr(probe, 'failure_threshold', 3),
        "success_threshold": getattr(probe, 'success_threshold', 1)
    }

    # Tipo de probe
    if probe.http_get:
        probe_info["type"] = "httpGet"
        probe_info["http_get"] = {
            "path": getattr(probe.http_get, 'path', '/'),
            "port": probe.http_get.port,
            "scheme": getattr(probe.http_get, 'scheme', 'HTTP')
        }
    elif probe.tcp_socket:
        probe_info["type"] = "tcpSocket"
        probe_info["tcp_socket"] = {"port": probe.tcp_socket.port}
    elif probe.exec:
        probe_info["type"] = "exec"
        probe_info["exec"] = {"command": probe.exec.command}

    return probe_info


def _extract_volume_info(volume) -> Dict[str, Any]:
    """Extrae información de volúmenes"""
    volume_info = {
        "name": volume.name,
        "type": "unknown",
        "details": {}
    }

    # Determinar tipo de volumen
    volume_types = {
        'empty_dir': 'emptyDir',
        'config_map': 'configMap',
        'secret': 'secret',
        'persistent_volume_claim': 'persistentVolumeClaim',
        'host_path': 'hostPath',
        'downward_api': 'downwardAPI',
        'projected': 'projected'
    }

    for attr, vol_type in volume_types.items():
        if hasattr(volume, attr) and getattr(volume, attr) is not None:
            volume_info["type"] = vol_type
            volume_info["details"] = _extract_volume_details(getattr(volume, attr), vol_type)
            break

    return volume_info


def _extract_volume_details(volume_source, vol_type: str) -> Dict[str, Any]:
    """Extrae detalles específicos del tipo de volumen"""
    details = {}

    if vol_type == "emptyDir":
        details["size_limit"] = getattr(volume_source, 'size_limit', None)
    elif vol_type == "configMap":
        details["name"] = getattr(volume_source, 'name', None)
        details["default_mode"] = getattr(volume_source, 'default_mode', None)
    elif vol_type == "secret":
        details["secret_name"] = getattr(volume_source, 'secret_name', None)
        details["default_mode"] = getattr(volume_source, 'default_mode', None)
    elif vol_type == "persistentVolumeClaim":
        details["claim_name"] = getattr(volume_source, 'claim_name', None)
        details["read_only"] = getattr(volume_source, 'read_only', False)
    elif vol_type == "hostPath":
        details["path"] = getattr(volume_source, 'path', None)
        details["type"] = getattr(volume_source, 'type', None)

    return details


def _extract_pod_status(pod) -> Dict[str, Any]:
    """Extrae estado del pod"""
    status = {
        "phase": pod.status.phase,
        "conditions": [],
        "container_statuses": [],
        "init_container_statuses": [],
        "host_ip": pod.status.host_ip,
        "pod_ip": pod.status.pod_ip,
        "start_time": pod.status.start_time.isoformat() if pod.status.start_time else None,
        "qos_class": getattr(pod.status, 'qos_class', None)
    }

    # Condiciones
    if pod.status.conditions:
        for condition in pod.status.conditions:
            status["conditions"].append({
                "type": condition.type,
                "status": condition.status,
                "last_transition_time": condition.last_transition_time.isoformat() if condition.last_transition_time else None,
                "reason": getattr(condition, 'reason', None),
                "message": getattr(condition, 'message', None)
            })

    # Estados de contenedores
    if pod.status.container_statuses:
        for container_status in pod.status.container_statuses:
            status["container_statuses"].append(_extract_container_status(container_status))

    # Estados de init containers
    if getattr(pod.status, 'init_container_statuses', None):
        for container_status in pod.status.init_container_statuses:
            status["init_container_statuses"].append(_extract_container_status(container_status))

    return status


def _extract_container_status(container_status) -> Dict[str, Any]:
    """Extrae estado de un contenedor"""
    status_info = {
        "name": container_status.name,
        "ready": container_status.ready,
        "restart_count": container_status.restart_count,
        "image": container_status.image,
        "image_id": getattr(container_status, 'image_id', None),
        "container_id": getattr(container_status, 'container_id', None),
        "state": {},
        "last_state": {}
    }

    # Estado actual
    if container_status.state:
        status_info["state"] = _extract_container_state(container_status.state)

    # Estado anterior
    if getattr(container_status, 'last_state', None):
        status_info["last_state"] = _extract_container_state(container_status.last_state)

    return status_info


def _extract_container_state(state) -> Dict[str, Any]:
    """Extrae estado específico de un contenedor"""
    if state.running:
        return {
            "status": "running",
            "started_at": state.running.started_at.isoformat() if state.running.started_at else None
        }
    elif state.waiting:
        return {
            "status": "waiting",
            "reason": getattr(state.waiting, 'reason', None),
            "message": getattr(state.waiting, 'message', None)
        }
    elif state.terminated:
        return {
            "status": "terminated",
            "exit_code": getattr(state.terminated, 'exit_code', None),
            "reason": getattr(state.terminated, 'reason', None),
            "message": getattr(state.terminated, 'message', None),
            "started_at": state.terminated.started_at.isoformat() if state.terminated.started_at else None,
            "finished_at": state.terminated.finished_at.isoformat() if state.terminated.finished_at else None
        }
    else:
        return {"status": "unknown"}


def _extract_pod_events(events: List) -> List[Dict[str, Any]]:
    """Extrae eventos del pod"""
    event_list = []

    for event in events:
        event_info = {
            "type": getattr(event, 'type', None),
            "reason": getattr(event, 'reason', None),
            "message": getattr(event, 'message', None),
            "first_timestamp": event.first_timestamp.isoformat() if event.first_timestamp else None,
            "last_timestamp": event.last_timestamp.isoformat() if event.last_timestamp else None,
            "count": getattr(event, 'count', 1),
            "source": getattr(event.source, 'component', None) if event.source else None,
            "object": {
                "kind": getattr(event.involved_object, 'kind', None),
                "name": getattr(event.involved_object, 'name', None),
                "namespace": getattr(event.involved_object, 'namespace', None)
            } if event.involved_object else None
        }
        event_list.append(event_info)

    # Ordenar eventos por timestamp
    event_list.sort(key=lambda x: x.get('last_timestamp') or x.get('first_timestamp') or '', reverse=True)

    return event_list


def _handle_api_exception(e: ApiException, pod_name: str, namespace: str) -> str:
    """Maneja excepciones de la API de Kubernetes"""
    if e.status == 404:
        return f"Pod '{pod_name}' no encontrado en el namespace '{namespace}'"
    elif e.status == 403:
        return f"Sin permisos para acceder al pod '{pod_name}' en el namespace '{namespace}'"
    elif e.status == 401:
        return "No autorizado para acceder a la API de Kubernetes"
    else:
        return f"Error de API de Kubernetes al obtener el pod '{pod_name}': {e}"
