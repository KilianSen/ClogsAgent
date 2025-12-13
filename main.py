import enum
from typing import LiteralString, Literal, List

import pydantic
import docker
from docker.models.containers import Container

from src.docker_api import get_monitored
from src.model.model import MONITORING_TYPE

MONITORING_TAG="clogs.monitoring.enabled=true"

def print_monitored_stacks_info(c: MONITORING_TYPE):
    for context, stacks in c.items():
        print(f"Context: {context.value}")
        for stack_name, containers in stacks.items():
            print(f"  Stack/Project Name: {stack_name}")
            for container in containers:
                print(f"    Container ID: {container.id[:12]}")
                print(f"    Container Name: {container.name}")
                print(f"    Container Status: {container.status}")
                print(f"    Container Image: {container.image.tags}")
                print(f"    Container Labels: {container.labels}")
                print(f"    Container Env: {container.attrs['Config']['Env']}")
                print()

if __name__ == "__main__":
    stacks = get_monitored(cross_stack_bounds=False)
    print_monitored_stacks_info(stacks)