-- Wipe all application data from interview_scheduler.
-- Keeps schema, alembic_version, and login accounts:
--   public.users            (HR / ADMIN / SUPERADMIN dashboard login)
--   agent5.admin_users      (Agent 5 admin login)
--
-- NOTE: TRUNCATE ... CASCADE would otherwise wipe public.users because
-- users.company_id references companies. We snapshot login rows first
-- and restore them after the wipe (company_id cleared).
--
-- Usage (Windows):
--   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h 127.0.0.1 -p 5432 -U postgres -d interview_scheduler -f backend\scripts\purge_all_data.sql
--
-- Usage (Linux VM):
--   sudo -u postgres psql -d interview_scheduler -f backend/scripts/purge_all_data.sql
--
-- After purge, sign in again (refresh tokens are cleared).

BEGIN;

-- Snapshot login accounts before CASCADE truncate can remove them.
CREATE TEMP TABLE _keep_users AS
SELECT * FROM public.users;

CREATE TEMP TABLE _keep_agent5_admins AS
SELECT * FROM agent5.admin_users;

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

-- Companies are required for jobs/candidates (FK). Re-seed defaults.
INSERT INTO public.companies (name, code, status)
VALUES
  ('RR Parkon', 'RRPARKON', 'active'),
  ('RR Kabel', 'RRKABEL', 'active')
ON CONFLICT (code) DO UPDATE
SET name = EXCLUDED.name, status = 'active';

SELECT setval(
  pg_get_serial_sequence('public.companies', 'id'),
  COALESCE((SELECT MAX(id) FROM public.companies), 1),
  true
);

-- Restore dashboard logins.
TRUNCATE TABLE public.users RESTART IDENTITY CASCADE;

INSERT INTO public.users (
  id, company_id, email, full_name, job_title, phone, password_hash, role, is_active, created_at, last_login_at
)
SELECT
  id,
  CASE
    WHEN role::text IN ('HR', 'ADMIN', 'COMPANY_ADMIN')
      THEN (SELECT id FROM public.companies WHERE code = 'RRPARKON' LIMIT 1)
    ELSE NULL
  END,
  email,
  full_name,
  job_title,
  phone,
  password_hash,
  role,
  is_active,
  created_at,
  NULL
FROM _keep_users
ON CONFLICT (email) DO NOTHING;

-- If the DB had no users before purge, seed the default RR accounts.
INSERT INTO public.users (email, full_name, password_hash, role, is_active, company_id)
SELECT
  v.email,
  v.full_name,
  v.password_hash,
  v.role::user_role,
  true,
  CASE
    WHEN v.role IN ('HR', 'ADMIN', 'COMPANY_ADMIN')
      THEN (SELECT id FROM public.companies WHERE code = 'RRPARKON' LIMIT 1)
    ELSE NULL
  END
FROM (
  VALUES
    -- SuperAdmin@1234
    ('superadmin@rrglobal.com', 'Super Admin',
     '$2b$12$J7zUmUun85aTiNNDfRigwuhe6TOUk7bIPqzKH476uGEzW0LfingJ2', 'SUPERADMIN'),
    -- rradmin@1234
    ('admin@rrglobal.com', 'RR Global Admin',
     '$2b$12$s2xWw6r7861r7XEKhrcSD.CmGSAxPRdzyrsSAPSswY4rr442c5pdu', 'ADMIN'),
    -- rrhr@12345
    ('rrhr@rrglobal.com', 'RR Global HR',
     '$2b$12$E2CCqooUQxHI2CGIQN6TAue7ptNHD.Ja1VTLSYKfGaxZEsC/Wh7BO', 'HR')
) AS v(email, full_name, password_hash, role)
WHERE NOT EXISTS (
  SELECT 1 FROM public.users u WHERE u.email = v.email
);

SELECT setval(
  pg_get_serial_sequence('public.users', 'id'),
  COALESCE((SELECT MAX(id) FROM public.users), 1),
  true
);

-- Restore Agent 5 admin logins if any existed.
TRUNCATE TABLE agent5.admin_users RESTART IDENTITY CASCADE;

INSERT INTO agent5.admin_users (id, username, password_hash, role, active, created_at)
SELECT id, username, password_hash, role, active, created_at
FROM _keep_agent5_admins
ON CONFLICT (username) DO NOTHING;

COMMIT;

\echo 'Application data deleted. Companies + login accounts restored:'
SELECT id, name, code, status FROM public.companies ORDER BY id;

SELECT id, email, full_name, role, company_id, is_active
FROM public.users
ORDER BY id;

SELECT id, username, role, active
FROM agent5.admin_users
ORDER BY username;
