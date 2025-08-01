#!/usr/bin/env python3

import argparse
import logging
import threading
import time
from datetime import datetime

from flask import Flask, Response
from prometheus_client import Gauge, generate_latest

from nodescraper.cli.helper import get_plugin_configs, get_system_info
from nodescraper.configregistry import ConfigRegistry
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.pluginexecutor import PluginExecutor
from nodescraper.pluginregistry import PluginRegistry

app = Flask(__name__)

# prom metrics
plugin_status = Gauge(
    "plugin_status", "Plugin status: 1=OK, 0=non-OK", ["nodename", "plugin", "status"]
)

plugin_last_info = Gauge(
    "plugin_info", "Plugin metadata from last run", ["nodename", "plugin", "status", "timestamp", "message"]
)


# fake main for metrics
# TODO: update for diff SKU/others
def update_metrics():
    try:
        logger = logging.getLogger("node-scraper-exporter")
        logger.setLevel(logging.INFO)

        plugin_reg = PluginRegistry()
        config_reg = ConfigRegistry()

        dummy_args = argparse.Namespace(
            sys_name=None,
            sys_sku=None,
            sys_platform=None,
            sys_location="LOCAL",
            sys_interaction_level="INTERACTIVE",
            system_config=None,
            plugin_configs=["NodeStatus"],
            connection_config=None,
        )

        system_info = get_system_info(dummy_args)
        nodename = system_info.name.lower().replace("-", "_").replace(".", "_")
        timestamp = datetime.now().strftime("%Y_%m_%d-%I_%M_%S_%p")

        plugin_configs = get_plugin_configs(
            plugin_config_input=dummy_args.plugin_configs,
            system_interaction_level=dummy_args.sys_interaction_level,
            built_in_configs=config_reg.configs,
            parsed_plugin_args={},
            plugin_subparser_map={},
        )

        executor = PluginExecutor(
            logger=logger,
            plugin_configs=plugin_configs,
            connections=None,
            system_info=system_info,
            log_path=None,
        )

        results = executor.run_queue()

        plugin_status.clear()
        plugin_last_info.clear()

        for result in results:
            plugin = result.source
            status = result.status.name
            message = result.message or "no message"

            status_value = 1 if result.status == ExecutionStatus.OK else 0

            plugin_status.labels(
                nodename=nodename,
                plugin=plugin,
                status=status,
            ).set(status_value)

            plugin_last_info.labels(
                nodename=nodename,
                plugin=plugin,
                timestamp=timestamp,
                message=message,
            ).set(1)

    except Exception as e:
        print("Exception in update_metrics():", e)


# loop
def update_metrics_loop(interval=300):
    while True:
        update_metrics()
        time.sleep(interval)


# flask route
@app.route("/metrics")
def metrics():
    update_metrics()
    return Response(generate_latest(), mimetype="text/plain")


# start exporter
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    thread = threading.Thread(target=update_metrics_loop, daemon=True)
    thread.start()
    app.run(host="0.0.0.0", port=9101)
