from kubernetes import client
from kubernetes.client.rest import ApiException
from config import logger, load_kube_config
import json
import datetime
from typing import Optional, Dict, Any


def get_deployments(
    context: str,
    namespace: Optional[str] = None
) -> str:
    """
    Devuelve los deployments de un clúster Kubernetes.

    Args:
        context: Nombre del contexto de Kubernetes a usar. Si es None, usa el contexto por defecto.
        namespace: Namespace específico para filtrar los deployments.
                  Si es None, devuelve de todos los namespaces.

    Returns:
        JSON string con el listado de deployments y metadatos.
    """
    try:
        load_kube_config(context=context)
        api = client.AppsV1Api()

        logger.info(
            "Obteniendo deployments%s",
            f" del namespace '{namespace}'" if namespace else " de todos los namespaces"
        )

        if namespace:
            deployments = api.list_namespaced_deployment(namespace)
        else:
            deployments = api.list_deployment_for_all_namespaces()

        deployment_list = []
        for deployment in deployments.items:
            # Información más completa del deployment
            deployment_info = {
                "name": deployment.metadata.name,
                "namespace": deployment.metadata.namespace,
                "replicas": {
                    "desired": deployment.spec.replicas or 0,
                    "available": deployment.status.available_replicas or 0,
                    "ready": deployment.status.ready_replicas or 0,
                    "updated": deployment.status.updated_replicas or 0
                },
                "labels": deployment.metadata.labels or {},
                "annotations": deployment.metadata.annotations or {},
                "creation_timestamp": deployment.metadata.creation_timestamp.isoformat() if deployment.metadata.creation_timestamp else None,
                "strategy": {
                    "type": deployment.spec.strategy.type if deployment.spec.strategy else "Unknown"
                },
                "status": {
                    "conditions": []
                }
            }

            # Agregar condiciones del deployment si existen
            if deployment.status.conditions:
                for condition in deployment.status.conditions:
                    deployment_info["status"]["conditions"].append({
                        "type": condition.type,
                        "status": condition.status,
                        "reason": condition.reason,
                        "message": condition.message,
                        "last_transition_time": condition.last_transition_time.isoformat() if condition.last_transition_time else None
                    })

            deployment_list.append(deployment_info)

        result = {
            "total_deployments": len(deployment_list),
            "namespace": namespace or "all",
            "deployments": deployment_list
        }

        logger.info("Obtenidos %d deployments exitosamente", len(deployment_list))
        return json.dumps(result, indent=2)

    except ApiException as e:
        error_msg = f"Error de API de Kubernetes al obtener deployments: {e.reason}"
        logger.error("%s - Status: %s", error_msg, e.status)
        return json.dumps({
            "error": error_msg,
            "status_code": e.status,
            "namespace": namespace
        }, indent=2)

    except Exception as e:
        error_msg = f"Error inesperado al obtener deployments: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return json.dumps({
            "error": error_msg,
            "namespace": namespace
        }, indent=2)


def scale_deployment(namespace: str, deployment_name: str, replicas: int) -> str:
    """
    Escala un deployment en un clúster Kubernetes.

    Args:
        namespace: Namespace del deployment.
        deployment_name: Nombre del deployment a escalar.
        replicas: Número deseado de réplicas (debe ser >= 0).

    Returns:
        JSON string con el resultado del escalado.
    """
    # Validaciones de entrada
    if not namespace or not deployment_name:
        error_msg = "namespace y deployment_name son requeridos"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)

    if replicas < 0:
        error_msg = "El número de réplicas debe ser mayor o igual a 0"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)

    try:
        load_kube_config()
        api = client.AppsV1Api()

        # Verificar que el deployment existe antes de escalarlo
        try:
            current_deployment = api.read_namespaced_deployment(
                name=deployment_name,
                namespace=namespace
            )
            current_replicas = current_deployment.spec.replicas or 0
        except ApiException as e:
            if e.status == 404:
                error_msg = f"Deployment '{deployment_name}' no encontrado en namespace '{namespace}'"
                logger.error(error_msg)
                return json.dumps({"error": error_msg}, indent=2)
            raise

        logger.info(
            "Escalando deployment '%s' en namespace '%s' de %d a %d réplicas",
            deployment_name, namespace, current_replicas, replicas
        )

        # Crear el cuerpo de la solicitud de escalado
        body = {"spec": {"replicas": replicas}}

        # Realizar la solicitud de escalado
        api.patch_namespaced_deployment_scale(
            name=deployment_name,
            namespace=namespace,
            body=body
        )

        result = {
            "message": f"Deployment '{deployment_name}' escalado exitosamente",
            "namespace": namespace,
            "deployment_name": deployment_name,
            "previous_replicas": current_replicas,
            "new_replicas": replicas,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }

        logger.info("Escalado completado exitosamente para deployment '%s'", deployment_name)
        return json.dumps(result, indent=2)

    except ApiException as e:
        error_msg = f"Error de API de Kubernetes al escalar deployment '{deployment_name}': {e.reason}"
        logger.error("%s - Status: %s", error_msg, e.status)
        return json.dumps({
            "error": error_msg,
            "status_code": e.status,
            "namespace": namespace,
            "deployment_name": deployment_name
        }, indent=2)

    except Exception as e:
        error_msg = f"Error inesperado al escalar deployment '{deployment_name}': {str(e)}"
        logger.error(error_msg, exc_info=True)
        return json.dumps({
            "error": error_msg,
            "namespace": namespace,
            "deployment_name": deployment_name
        }, indent=2)


def rollout_deployment(namespace: str, deployment_name: str) -> str:
    """
    Realiza un rollout (reinicio) de un deployment en un clúster Kubernetes.

    Args:
        namespace: Namespace del deployment.
        deployment_name: Nombre del deployment a reiniciar.

    Returns:
        JSON string con el resultado del rollout.
    """
    # Validaciones de entrada
    if not namespace or not deployment_name:
        error_msg = "namespace y deployment_name son requeridos"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)

    try:
        load_kube_config()
        api = client.AppsV1Api()

        # Verificar que el deployment existe antes de hacer rollout
        try:
            current_deployment = api.read_namespaced_deployment(
                name=deployment_name,
                namespace=namespace
            )
        except ApiException as e:
            if e.status == 404:
                error_msg = f"Deployment '{deployment_name}' no encontrado en namespace '{namespace}'"
                logger.error(error_msg)
                return json.dumps({"error": error_msg}, indent=2)
            raise

        restart_timestamp = datetime.datetime.utcnow().isoformat()

        logger.info(
            "Realizando rollout del deployment '%s' en namespace '%s'",
            deployment_name, namespace
        )

        # Crear el cuerpo de la solicitud de actualización
        body = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "kubectl.kubernetes.io/restartedAt": restart_timestamp
                        }
                    }
                }
            }
        }

        # Realizar la solicitud de actualización
        api.patch_namespaced_deployment(
            name=deployment_name,
            namespace=namespace,
            body=body
        )

        result = {
            "message": f"Rollout realizado exitosamente para deployment '{deployment_name}'",
            "namespace": namespace,
            "deployment_name": deployment_name,
            "restarted_at": restart_timestamp,
            "current_replicas": current_deployment.spec.replicas or 0
        }

        logger.info("Rollout completado exitosamente para deployment '%s'", deployment_name)
        return json.dumps(result, indent=2)

    except ApiException as e:
        error_msg = f"Error de API de Kubernetes al realizar rollout del deployment '{deployment_name}': {e.reason}"
        logger.error("%s - Status: %s", error_msg, e.status)
        return json.dumps({
            "error": error_msg,
            "status_code": e.status,
            "namespace": namespace,
            "deployment_name": deployment_name
        }, indent=2)

    except Exception as e:
        error_msg = f"Error inesperado al realizar rollout del deployment '{deployment_name}': {str(e)}"
        logger.error(error_msg, exc_info=True)
        return json.dumps({
            "error": error_msg,
            "namespace": namespace,
            "deployment_name": deployment_name
        }, indent=2)


# Funciones auxiliares para uso interno
def get_deployments_dict(namespace: Optional[str] = None) -> Dict[str, Any]:
    """Versión que retorna un diccionario en lugar de JSON string."""
    deployments_json = get_deployments(namespace)
    return json.loads(deployments_json)


def get_deployment_status(namespace: str, deployment_name: str) -> Dict[str, Any]:
    """
    Obtiene el estado detallado de un deployment específico.

    Args:
        namespace: Namespace del deployment.
        deployment_name: Nombre del deployment.

    Returns:
        Diccionario con el estado del deployment.
    """
    try:
        load_kube_config()
        api = client.AppsV1Api()

        deployment = api.read_namespaced_deployment(
            name=deployment_name,
            namespace=namespace
        )

        return {
            "name": deployment.metadata.name,
            "namespace": deployment.metadata.namespace,
            "generation": deployment.metadata.generation,
            "observed_generation": deployment.status.observed_generation,
            "replicas": {
                "desired": deployment.spec.replicas or 0,
                "available": deployment.status.available_replicas or 0,
                "ready": deployment.status.ready_replicas or 0,
                "updated": deployment.status.updated_replicas or 0,
                "unavailable": deployment.status.unavailable_replicas or 0
            },
            "conditions": [
                {
                    "type": condition.type,
                    "status": condition.status,
                    "reason": condition.reason,
                    "message": condition.message
                }
                for condition in (deployment.status.conditions or [])
            ]
        }
    except Exception as e:
        logger.error("Error al obtener estado del deployment '%s': %s", deployment_name, e)
        return {"error": str(e)}
