# -*- coding: utf-8 -*-
import logging
import logging.config
import sys
from modules import graph_generator
from os import path


def main(*args):
    logger = configure_logging()
    generator = graph_generator.GraphGenerator()
    generator.run()


def configure_logging():
    log_config_path = path.join(path.dirname(path.abspath(__file__)), "config/logging.conf")
    logging.config.fileConfig(log_config_path, disable_existing_loggers=False)
    logger = logging.getLogger()
    return logger


if __name__ == "__main__":
    main(*sys.argv[1:])
