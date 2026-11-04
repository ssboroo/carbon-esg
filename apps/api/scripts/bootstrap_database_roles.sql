-- Execute once as a PostgreSQL administrator against the target database.
-- Set independent strong passwords through your secret manager after creating roles.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'carbon_esg_migrator') THEN
        CREATE ROLE carbon_esg_migrator
            LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOINHERIT BYPASSRLS;
    ELSE
        ALTER ROLE carbon_esg_migrator
            LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOINHERIT BYPASSRLS;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'carbon_esg_app') THEN
        CREATE ROLE carbon_esg_app
            LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOINHERIT NOBYPASSRLS;
    ELSE
        ALTER ROLE carbon_esg_app
            LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOINHERIT NOBYPASSRLS;
    END IF;
END
$$;

SELECT format('GRANT CONNECT ON DATABASE %I TO carbon_esg_migrator, carbon_esg_app', current_database()) \gexec
ALTER SCHEMA public OWNER TO carbon_esg_migrator;
GRANT USAGE, CREATE ON SCHEMA public TO carbon_esg_migrator;
