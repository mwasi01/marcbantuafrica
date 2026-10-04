-- ============================================================
-- MIGRATION 008 — Add sync fields to records
-- ============================================================

ALTER TABLE records ADD COLUMN client_id TEXT;
ALTER TABLE records ADD COLUMN sync_source TEXT DEFAULT 'online';

CREATE INDEX idx_records_client ON records(client_id);
CREATE INDEX idx_records_sync_source ON records(sync_source);