DROP FUNCTION IF EXISTS public."initLeagueGraphs"(character varying, character varying, character varying, character varying);

CREATE OR REPLACE FUNCTION public."initLeagueGraphs"(
    _database_db character varying,
    _username_db character varying,
    _password_db character varying,
    _password_pg character varying
)
RETURNS INTEGER
LANGUAGE 'plpgsql'
COST 100
VOLATILE PARALLEL UNSAFE
AS $BODY$
BEGIN
    CREATE EXTENSION IF NOT EXISTS dblink;

    -- Create database if it doesn't exist
    IF EXISTS (SELECT FROM pg_database WHERE datname = _database_db) THEN
        RAISE NOTICE 'Database % already exists, skipping', _database_db;
    ELSE
        PERFORM dblink_exec(
            'dbname=postgres user=postgres password=' || _password_pg,
            'CREATE DATABASE ' || _database_db);
    END IF;

    -- Create database user if it doesn't exist
    IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = _username_db) THEN
        RAISE NOTICE 'Role % already exists, skipping', _username_db;
    ELSE
        EXECUTE format('CREATE ROLE %I WITH LOGIN CREATEDB CREATEROLE PASSWORD %L', _username_db, _password_db);
        EXECUTE format('GRANT ALL PRIVILEGES ON DATABASE %I to %I', _database_db,_username_db);
    END IF;

    RETURN 0;
END;
$BODY$;
