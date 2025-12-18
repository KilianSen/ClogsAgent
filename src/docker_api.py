import logging
from functools import lru_cache
from typing import List

from docker import errors
from docker import from_env
from docker.models.containers import Container

from src.config import Config
from src.model.model import Context, MONITORING_TYPE

logger = logging.getLogger(__name__)
MONITORING_TAG = Config.MONITORING_TAG

client = from_env()

@lru_cache(maxsize=1)
def get_executor() -> tuple[Context, str | None]:
    """
    Determines the context and name of the current executor container.
    It first tries to get the container ID from the hostname or /proc files,
    then retrieves the container object and its labels to determine the context.
    :return: A tuple of (Context, container name or None)
    """
    used_hostname = False
    container_id = None
    try:
        # Method 1: Check hostname (Docker sets it to container ID by default)
        import socket
        hostname = socket.gethostname()

        # Method 2: Check /proc/1/cpuset or /proc/self/mountinfo for container ID
        for path in ['/proc/1/cpuset', '/proc/self/cgroup']:
            try:
                with open(path, 'r') as f:
                    content = f.read().strip()
                    # Extract container ID from path (works for both cgroups v1 and v2)
                    for segment in content.split('/'):
                        if len(segment) == 64 or len(segment) == 12:  # Full or short container ID
                            container_id = segment
                            break
                if container_id:
                    break
            except FileNotFoundError:
                logger.debug(f"File {path} not found, skipping.")
                continue

        # Fallback: try hostname as container ID
        if not container_id:
            container_id = hostname
            used_hostname = True
            logger.info(f"Determining container ID failed, using hostname: {container_id}")

        return get_container_context(client.containers.get(container_id))
    except errors.NotFound:
        if not used_hostname:
            logger.warning(f"Container with ID {container_id} not found.")
        if used_hostname:
            logger.info(f"No container found for ID derived from hostname: {container_id}, most likely running outside a container.")
        return Context.host, None
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Context.orphan, None

def get_container_context(container: Container) -> tuple[Context, str | None]:
    try:
        executor_container = container
        executor_labels = executor_container.labels

        stack_name = executor_labels.get('com.docker.stack.namespace')
        if stack_name is not None:
            executor_context = Context.stack
            executor_name = stack_name
            return executor_context, executor_name

        compose_name = executor_labels.get('com.docker.compose.project')
        if compose_name is not None:
            executor_context = Context.compose
            executor_name = compose_name
            return executor_context, executor_name

        return Context.orphan, None
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Context.orphan, None

def filter_by_tags(all_containers: list[Container], tag_filter: List[str] | None) -> list[Container]:
    """
    Filters the given list of containers by the given tag filter.
    If no tag filter is given, it checks if any container has the default monitoring tag, and if so, it filters by that tag.
    If a tag filter is given, it filters by the given tags.
    If no tags are given, it returns all containers.

    :param all_containers: List of all containers to filter.
    :param tag_filter: List of tags to filter by.
    :return: List of filtered containers.
    """

    internal_filter = [] if tag_filter is None else tag_filter.copy()

    if tag_filter is None:
        # Check if any container has the monitoring tag
        monitoring_tagged_containers = [c for c in all_containers if c.labels and c.labels.get(MONITORING_TAG.split('=')[0]) == MONITORING_TAG.split('=')[1]]
        if len(monitoring_tagged_containers) > 0:
            internal_filter.append(MONITORING_TAG)

    if tag_filter is not None and len(tag_filter) > 0 or len(internal_filter) > 0:
        filtered_containers = []
        for container in all_containers:
            container.reload()
            labels = container.labels
            if labels is None:
                continue

            for tag in internal_filter:
                key_value = tag.split('=', 1)
                key = key_value[0]
                value = key_value[1] if len(key_value) > 1 else None

                if key in labels:
                    if value is None or labels[key] == value:
                        filtered_containers.append(container)
                        break  # No need to check other tags for this container

        return filtered_containers
    return all_containers

def get_monitored(containers: List[Container] | None = None, tag_filter: List[str] = None, cross_containerization_bounds: bool = False, executor: tuple[Context, str] | None = None) -> MONITORING_TYPE:
    """
    Gets all monitored containers, grouped by their context (orphan, compose, stack) and name.
    :param executor: Tuple of (Context, container name or None) representing the executor container.
    :param containers: List of containers to check.
    :param tag_filter: List of tags to filter by. (See `filter_by_tags` for details.)
    :param cross_containerization_bounds: Whether to include containers from other contexts.
    :return: Dictionary of monitored containers.
    """
    if containers is None:
        containers = client.containers.list(all=True)

    if executor is None:
        executor = get_executor()

    if executor[0] == Context.host:
        # If running on host, monitor all containers regardless of context (tag filtering still applies)
        cross_containerization_bounds = True

    monitored: MONITORING_TYPE = {}
    for container in filter_by_tags(containers, tag_filter):
        container.reload()
        container_context, container_context_name = get_container_context(container)

        # Todo: If executed as single container in compose/stack, this would result in no monitored containers.
        # Decide if this is the desired behavior. Probably sensible to add config option to allow cross-boundary monitoring on single container stacks/compose setups.
        if not cross_containerization_bounds and executor != (container_context, container_context_name):
            continue


        if container_context not in monitored:
            monitored[container_context] = {}

        if container_context_name not in monitored[container_context]:
            monitored[container_context][container_context_name] = []

        monitored[container_context][container_context_name].append(container)

    return monitored
