# -*- coding: utf-8 -*-
from .main import ROOT_DIR
from collections.abc import Generator
from contextlib import contextmanager
from os import getenv, path
import logging
import psycopg2

logger = logging.getLogger(__name__)


class DBConnector(object):
    """Provides tools for connecting to a PostgreSQL database"""
    def __init__(self, config : dict):
        """Initiate PostgreSQL database connection using the configuration at database.conf

        :param config: Dictionary with psycopg2 connection configurations."""
        # Gather "postgres" database configurations and store on self.config_pg
        config_pg = dict(config.get("database_pg").items())
        password_pg = getenv("POSTGRES_DB_PW")
        config_pg["password"] = password_pg
        self.config_pg = config_pg

        # Gather "league_graphs" database configurations and store on self.config_db
        config_db = dict(config.get("database_db").items())
        password_db = getenv("LEAGUE_GRAPHS_DB_PW")
        config_db["password"] = password_db
        database_db = config_db["database"]
        user_db = config_db["user"]
        self.config_db = config_db

        # Connect to "postgres" database and run initialization procedure
        with self.connect_to_db_ctx(config_pg) as cr:
            cr.connection.autocommit = True
            with open(path.join(ROOT_DIR, "sql/initLeagueGraphs.sql")) as fp:
                cr.execute(fp.read())

            try:
                cr.execute(f"SELECT \"initLeagueGraphs\"({database_db!r}, {user_db!r}, {password_db!r}, {password_pg!r});")
            except:
                logger.exception(f"Error while attempting to configure database {database_db}")

            logger.info(f"Successfully configured database {database_db}")

        # Connect to app database "league_graphs"
        self.cr = self.connect_to_db(config_db)

    def __enter__(self):
        """Default context manager starting method"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Default context manager starting method"""
        self.close()

    def connect_to_db(self, config : dict) -> psycopg2.extensions.cursor:
        """Establish a connection to a database and return a cursor.

        :param config: Dictionary containing database name, user and password for connection."""
        try:
            connection = psycopg2.connect(**config)
            cr = connection.cursor()
        except Exception as e:
            logger.exception(f"Unable to connect to database {config['database']}")
            raise e
        logger.info(f"Successfully connected to database {config['database']}")
        return cr

    @contextmanager
    def connect_to_db_ctx(self, config : dict) -> Generator[psycopg2.extensions.cursor]:
        """Establish a connection to a database as a context manager.

        :param config: Dictionary containing database name, user and password for connection."""
        cr = self.connect_to_db(config)
        yield cr
        cr.close()
        cr.connection.close()
        logger.info(f"Closed cursor and connection to {config['database']}")

    def close(self):
        """Close PostgreSQL cursor and connection"""
        database = self.cr.connection.info.dbname
        self.cr.close()
        self.cr.connection.close()
        logger.info(f"Closed cursor and connection to {database}")
