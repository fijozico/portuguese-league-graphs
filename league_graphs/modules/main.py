# -*- coding: utf-8 -*-
from modules import db_connector, graph_generator
from dotenv import load_dotenv
from os import path
import configparser
import logging
import logging.config

ROOT_DIR = path.abspath("league_graphs")
ENV_CONFIG_PATH = "config/.env"
CONFIG_PATH = "config/league_graphs.conf"
LOGGER_CONFIG_PATH = "config/logging.conf"


def main():
    load_dotenv(path.join(ROOT_DIR, ENV_CONFIG_PATH))
    config = get_config()
    logger = get_logger()
    db = db_connector.DBConnector(config)
    generator = graph_generator.GraphGenerator()
    generator.run()
    db.close()


def get_config() -> dict:
    """Parse main configuration file and convert it to a dictionary"""
    config = configparser.ConfigParser()
    config.read(path.join(ROOT_DIR, CONFIG_PATH))
    return dict(config)


def get_logger() -> logging.Logger:
    """Configure base logger with settings coming from logging.conf"""
    log_config_path = path.join(ROOT_DIR, LOGGER_CONFIG_PATH)
    logging.config.fileConfig(log_config_path, disable_existing_loggers=False)
    logger = logging.getLogger()
    return logger
