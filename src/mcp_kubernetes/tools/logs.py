import json
from typing import Optional, Dict, Any
from kubernetes import client
from kubernetes.client.rest import ApiException
from config import logger, load_kube_config
from typing import Optional, Dict, Any


def get_logs(
    context: str,
    environment: str,
    pod_name: str,
    namespace: str,
    container: Optional[str] = None,
    previous: bool = False,
    tail_lines: int = 100
) -> str:
    """
    Obtiene los logs de un pod específico en Kubernetes.

    Args:
        context: Nombre del contexto de Kubernetes a usar. Si es None, usa el contexto por defecto.
        environment: Entorno donde se ejecuta el pod
        pod_name: Nombre del pod
        namespace: Namespace del pod
        container: Nombre del contenedor específico (opcional)
        previous: Si obtener logs del contenedor anterior (opcional)
        tail_lines: Número de líneas finales a obtener (default: 100)

    Returns:
        JSON string con los logs o error
    """
    if not pod_name or not namespace:
        error_msg = "pod_name y namespace son requeridos"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}, indent=2)

    if tail_lines <= 0:
        tail_lines = 100
        logger.warning("tail_lines debe ser positivo, usando valor por defecto: 100")

    try:
        load_kube_config(context=context)
        api = client.CoreV1Api()

        # Preparar parámetros para la llamada a la API
        log_params = {
            'name': pod_name,
            'namespace': namespace,
            'tail_lines': tail_lines,
            'previous': previous
        }

        if container:
            log_params['container'] = container

        logger.info(
            "Obteniendo logs del pod '%s' en namespace '%s'%s",
            pod_name,
            namespace,
            f" del contenedor '{container}'" if container else ""
        )

        logs = api.read_namespaced_pod_log(**log_params)

        result = {
            "pod_name": pod_name,
            "namespace": namespace,
            "container": container,
            "lines_count": len(logs.splitlines()) if logs else 0,
            "logs": logs
        }

        logger.info("Logs obtenidos exitosamente para el pod '%s'", pod_name)
        return json.dumps(result, indent=2)

    except ApiException as e:
        error_msg = f"Error de API de Kubernetes al obtener logs del pod '{pod_name}': {e.reason}"
        logger.error("%s - Status: %s", error_msg, e.status)

        return json.dumps({
            "error": error_msg,
            "status_code": e.status,
            "pod_name": pod_name,
            "namespace": namespace
        }, indent=2)

    except Exception as e:
        error_msg = f"Error inesperado al obtener logs del pod '{pod_name}': {str(e)}"
        logger.error(error_msg, exc_info=True)

        return json.dumps({
            "error": error_msg,
            "pod_name": pod_name,
            "namespace": namespace
        }, indent=2)


def get_logs_dict(
    environment: str,
    pod_name: str,
    namespace: str,
    container: Optional[str] = None,
    previous: bool = False,
    tail_lines: int = 100
) -> Dict[str, Any]:
    """
    Versión que retorna un diccionario en lugar de JSON string.
    Útil para uso interno sin necesidad de serialización.
    """
    logs_json = get_logs(environment, pod_name, namespace, container, previous, tail_lines)
    return json.loads(logs_json)
