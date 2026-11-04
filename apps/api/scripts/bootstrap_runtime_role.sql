-- Execute as the database owner using psql.
-- Set a strong password for carbon_esg_app separately after this script.
DO $$
BEGIN
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

SELECT format('GRANT CONNECT ON DATABASE %I TO carbon_esg_app', current_database()) \gexec
GRANT USAGE ON SCHEMA public TO carbon_esg_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO carbon_esg_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO carbon_esg_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO carbon_esg_app;

-- Future application tables created by the migration owner inherit the same DML grants.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO carbon_esg_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO carbon_esg_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO carbon_esg_app;
