-- Run this once in pgAdmin Query Tool if you want the dashboard screenshot
-- to show all three urgency buckets: Low, Medium, High.
-- UI mapping used by the project:
--   normal   -> Low
--   urgent   -> Medium
--   critical -> High

-- Keep at least one customer message as Low.
WITH one_low AS (
    SELECT id
    FROM messages
    WHERE sender_type = 'customer'
    ORDER BY created_at DESC NULLS LAST, id DESC
    OFFSET 2 LIMIT 1
)
UPDATE messages
SET urgency = 'normal',
    urgency_confidence = 0.90,
    corrected_urgency = NULL
WHERE id IN (SELECT id FROM one_low);

-- Keep at least one customer message as Medium.
WITH one_medium AS (
    SELECT id
    FROM messages
    WHERE sender_type = 'customer'
    ORDER BY created_at DESC NULLS LAST, id DESC
    OFFSET 1 LIMIT 1
)
UPDATE messages
SET urgency = 'urgent',
    urgency_confidence = 0.90,
    routing_action = COALESCE(routing_action, 'human_handoff'),
    corrected_urgency = NULL
WHERE id IN (SELECT id FROM one_medium);

-- Keep at least one customer message as High.
WITH one_high AS (
    SELECT id
    FROM messages
    WHERE sender_type = 'customer'
    ORDER BY created_at DESC NULLS LAST, id DESC
    LIMIT 1
)
UPDATE messages
SET urgency = 'critical',
    urgency_confidence = 0.95,
    routing_action = 'escalation',
    needs_human = true,
    corrected_urgency = NULL,
    routing_reason = COALESCE(routing_reason, '') || '; demo_high_bucket'
WHERE id IN (SELECT id FROM one_high);

-- Check result:
SELECT urgency, COUNT(*)
FROM messages
WHERE sender_type = 'customer'
GROUP BY urgency
ORDER BY urgency;
