-- Wipe all application data from interview_scheduler.
-- Keeps schema, alembic_version, and login accounts:
--   public.users            (HR / ADMIN dashboard login)
--   agent5.admin_users      (Agent 5 admin login)
--
-- Usage:
--   psql -h 127.0.0.1 -p 5432 -U postgres -d interview_scheduler -f backend/scripts/purge_all_data.sql
--
-- After purge, log in with the existing HR/admin credentials.
-- Refresh tokens are cleared, so you must sign in again.

BEGIN;

DO $$
DECLARE
  tables text;
BEGIN
  SELECT string_agg(format('%I.%I', n.nspname, c.relname), ', ' ORDER BY n.nspname, c.relname)
  INTO tables
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE c.relkind = 'r'
    AND n.nspname IN ('public', 'agent5')
    AND c.relname NOT IN ('users', 'admin_users', 'alembic_version');

  IF tables IS NULL THEN
    RAISE NOTICE 'No application tables found to truncate.';
    RETURN;
  END IF;

  EXECUTE format('TRUNCATE TABLE %s RESTART IDENTITY CASCADE', tables);
  RAISE NOTICE 'Truncated: %', tables;
END $$;

COMMIT;

\echo 'Application data deleted. Login accounts kept:'
SELECT id, email, full_name, role, is_active
FROM public.users
ORDER BY id;

SELECT id, username, role, active
FROM agent5.admin_users
ORDER BY username;
