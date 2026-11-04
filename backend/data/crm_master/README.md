# Demo data assets (CRM already loaded in Supabase)

Seeding scripts and intermediate JSON were removed. The 200-row `revenue_recovery.crm_master` dataset lives in the database.

## Kept here

| Path | Why |
|---|---|
| `knowledge_base/` | Feature 4 source documents (embed at event time) |
| `sample_meetings/` | Feature 3 live-upload demo files (not stored in JSONB) |
| `schema.sql` | Table reference (includes `uploaded_meetings`) |

## Product docs

Project PRDs and design docs stay under `docs/` at the repo root.
