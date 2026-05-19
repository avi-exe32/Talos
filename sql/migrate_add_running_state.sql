-- Migration: Add 'Running' state to agent_log lifecycle_state constraint
-- This allows agents to log when they START processing, not just when they finish

-- Drop the old constraint
ALTER TABLE agent_log DROP CONSTRAINT IF EXISTS agent_log_lifecycle_state_check;

-- Add the new constraint with 'Running' included
ALTER TABLE agent_log ADD CONSTRAINT agent_log_lifecycle_state_check 
    CHECK (lifecycle_state IN ('Running', 'Pending', 'Executed', 'Rejected'));

-- Verify the change
SELECT conname, pg_get_constraintdef(oid) 
FROM pg_constraint 
WHERE conrelid = 'agent_log'::regclass 
  AND conname = 'agent_log_lifecycle_state_check';

-- Made with Bob
