# Clogs - Agent

_About Clogs_: Clogs, short for "Container Log Status", is three part toolset, to provide visibility into container/stack logs, and their health status. Think of it as an easily deployable statuspage alternative, with more insights into your container logs. See the [main README]() for more information.

The Clogs Agent is a lightweight service that sources logs/metrics from your containers, and ships them to the Clogs Backend for processing and visualization.

It can be deployed as a standalone container, or as part of a compose stack.

If deployed as part of a compose stack, it can automatically discover other containers in the same stack, and start monitoring their logs/metrics.
If deployed standalone, by default it will monitor all containers on the host, but can be configured to monitor specific containers only.

## Agent Protocol
The Clogs Agent communicates with the Clogs Backend via a simple HTTP API.

It sends a heartbeat every 30 seconds to indicate that it is alive.

