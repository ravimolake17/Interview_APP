-- Delete all history for one RR candidate.
-- Usage (PowerShell, from repo root):
--   psql -h 127.0.0.1 -p 5432 -U postgres -d interview_scheduler -f backend/scripts/delete_candidate.sql
--
-- Change this id before running:
\set candidate_id 'CAND-1050BDD1'

\echo 'Preview candidate:'
SELECT candidate_id, full_name, email, status, job_position, created_at
FROM candidate
WHERE candidate_id = :'candidate_id';

\echo 'Preview interview rows:'
SELECT id, scheduled_date, scheduled_time, status
FROM interview
WHERE candidate_id = :'candidate_id';

\echo 'Preview Agent5 sessions:'
SELECT s.id, s.status, s.termination_reason, s.tab_switch_count, s.risk_score
FROM agent5.audit_logs al
JOIN agent5.sessions s ON s.id = al.target_id
WHERE al.action = 'candidate_registered_from_rr'
  AND al.actor_id = :'candidate_id';

BEGIN;

UPDATE available_slots
SET booked_candidate = NULL,
    is_booked = FALSE
WHERE booked_candidate = :'candidate_id';

DELETE FROM interview
WHERE candidate_id = :'candidate_id';

DELETE FROM schedule_token
WHERE candidate_id = :'candidate_id';

DELETE FROM interview_blueprint
WHERE candidate_id = :'candidate_id';

DELETE FROM hr_recommendation_reports
WHERE candidate_id = :'candidate_id';

DELETE FROM interview_evaluations
WHERE candidate_id = :'candidate_id';

DELETE FROM audit_logs
WHERE entity_type = 'candidate'
  AND entity_id = :'candidate_id';

-- LangGraph checkpoints (created at backend startup by AsyncPostgresSaver.setup)
SELECT EXISTS (
  SELECT 1 FROM information_schema.tables
  WHERE table_schema = 'public' AND table_name = 'checkpoint_writes'
) AS has_checkpoint_writes \gset

\if :has_checkpoint_writes
DELETE FROM checkpoint_writes
WHERE thread_id LIKE 'scheduler-' || :'candidate_id' || '%'
   OR thread_id LIKE 'interview-' || :'candidate_id' || '%'
   OR thread_id LIKE 'blueprint-' || :'candidate_id' || '%'
   OR thread_id LIKE 'evaluation-' || :'candidate_id' || '%'
   OR thread_id LIKE 'recommendation-' || :'candidate_id' || '%'
   OR thread_id LIKE 'screening-' || :'candidate_id' || '%';

DELETE FROM checkpoint_blobs
WHERE thread_id LIKE 'scheduler-' || :'candidate_id' || '%'
   OR thread_id LIKE 'interview-' || :'candidate_id' || '%'
   OR thread_id LIKE 'blueprint-' || :'candidate_id' || '%'
   OR thread_id LIKE 'evaluation-' || :'candidate_id' || '%'
   OR thread_id LIKE 'recommendation-' || :'candidate_id' || '%'
   OR thread_id LIKE 'screening-' || :'candidate_id' || '%';

DELETE FROM checkpoints
WHERE thread_id LIKE 'scheduler-' || :'candidate_id' || '%'
   OR thread_id LIKE 'interview-' || :'candidate_id' || '%'
   OR thread_id LIKE 'blueprint-' || :'candidate_id' || '%'
   OR thread_id LIKE 'evaluation-' || :'candidate_id' || '%'
   OR thread_id LIKE 'recommendation-' || :'candidate_id' || '%'
   OR thread_id LIKE 'screening-' || :'candidate_id' || '%';
\endif

DELETE FROM agent5.sessions
WHERE id IN (
  SELECT al.target_id
  FROM agent5.audit_logs al
  WHERE al.action = 'candidate_registered_from_rr'
    AND al.actor_id = :'candidate_id'
    AND al.target_id IS NOT NULL
);

DELETE FROM agent5.audit_logs
WHERE actor_id = :'candidate_id'
   OR target_id IN (
     SELECT al.target_id
     FROM agent5.audit_logs al
     WHERE al.action = 'candidate_registered_from_rr'
       AND al.actor_id = :'candidate_id'
       AND al.target_id IS NOT NULL
   );

DELETE FROM agent5.candidates c
WHERE NOT EXISTS (
  SELECT 1 FROM agent5.sessions s WHERE s.candidate_id = c.id
)
AND c.email = (
  SELECT lower(email) FROM candidate WHERE candidate_id = :'candidate_id' LIMIT 1
);

DELETE FROM candidate
WHERE candidate_id = :'candidate_id';

COMMIT;

\echo 'Done. Candidate should be gone:'
SELECT candidate_id FROM candidate WHERE candidate_id = :'candidate_id';
