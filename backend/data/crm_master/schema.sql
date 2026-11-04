-- crm_master: the single CRM table for the AI Revenue Intelligence hackathon demo.
-- One row = one institutional sales opportunity or potential lead (simulated CRM record about a real,
-- publicly identified institution). Run once in the Supabase SQL editor, or through insert_crm_data.py.
-- Safe to re-run: every statement is idempotent.

create extension if not exists vector;                       -- already enabled; not used by this table
create schema if not exists revenue_recovery;

create table if not exists revenue_recovery.crm_master (
    -- ===== A. Institution and account =====
    id                              uuid primary key,
    account_id                      text not null unique,
    account_name                    text not null,
    account_type                    text not null,          -- Education | Government | Corporate
    institution_category            text not null,          -- University, College, School, ...
    industry                        text,
    country                         text not null,
    state                           text,
    city                            text,
    website                         text,
    organization_description        text,
    approximate_student_population  integer,                -- illustrative, SYNTHETIC
    approximate_employee_count      integer,                -- illustrative, SYNTHETIC
    account_priority                text,                   -- high | medium | low
    account_status                  text,
    account_owner                   text,                   -- synthetic sales rep name
    data_classification             text not null,          -- PUBLIC_VERIFIED | SYNTHETIC | AI_GENERATED (account identity)

    -- ===== B. Contact (all synthetic) =====
    contact_id                      text,
    contact_name                    text,
    contact_designation             text,
    contact_department              text,
    contact_role                    text,                   -- champion | decision_maker | influencer | it | procurement | finance | user
    is_decision_maker               boolean,
    contact_email                   text,                   -- example.com only
    contact_phone                   text,                   -- always null: phone numbers are not stored
    contact_status                  text,

    -- ===== C. Lead =====
    lead_id                         text,
    lead_source                     text,
    lead_category                   text,
    product_interest                text,
    lead_status                     text,
    lead_score                      integer check (lead_score between 0 and 100),
    qualification_status            text,
    lead_created_date               date,
    last_contacted_date             date,
    last_activity_date              date,
    next_followup_date              date,
    inactivity_days                 integer check (inactivity_days >= 0),
    lead_owner                      text,
    lost_reason                     text,
    recovery_eligibility            text,                   -- eligible | not_eligible | review

    -- ===== D. Opportunity and revenue =====
    opportunity_id                  text,
    opportunity_name                text,
    product_category                text,
    solution_description            text,
    opportunity_stage               text,
    deal_value                      numeric(14,2) check (deal_value >= 0),
    currency                        text,
    win_probability                 integer check (win_probability between 0 and 100),
    weighted_pipeline_value         numeric(14,2),          -- deal_value * win_probability / 100
    expected_close_date             date,
    actual_close_date               date,
    deal_status                     text,                   -- open | won | lost | stalled | inactive | none
    competitor_category             text,
    competitor_notes                text,
    strategic_account               boolean,
    revenue_risk_score              integer check (revenue_risk_score between 0 and 100),   -- AI_GENERATED
    opportunity_score               integer check (opportunity_score between 0 and 100),    -- AI_GENERATED
    risk_category                   text,                   -- high | medium | low
    risk_reason                     text,                   -- AI_GENERATED
    recommended_next_action         text,                   -- AI_GENERATED

    -- ===== E. Sales activity =====
    activity_type                   text,
    activity_date                   date,
    activity_description            text,
    activity_outcome                text,
    previous_interaction_summary    text,
    next_action                     text,
    next_action_date                date,
    sales_engagement_count          integer check (sales_engagement_count >= 0),
    activity_history                jsonb,                  -- array of past activities (synthetic)

    -- ===== F. Meeting intelligence =====
    meeting_date                    date,
    meeting_type                    text,
    meeting_summary                 text,
    meeting_transcript              text,
    customer_requirements           jsonb,
    pain_points                     jsonb,
    budget_discussion               text,
    purchase_timeline               text,
    customer_objections             jsonb,
    stakeholders                    jsonb,
    competitor_mentions             jsonb,
    decision_criteria               jsonb,
    extracted_action_items          jsonb,
    customer_commitments            jsonb,
    meeting_insights                jsonb,                  -- AI_GENERATED
    -- Live uploads only. Pre-generated meeting_* columns above are never overwritten by an upload.
    -- Each element is one meeting object (meeting_id, file path, transcript, extractions, status).
    -- Default empty array. Append only; never replace the whole array with a single object.
    uploaded_meetings               jsonb not null default '[]'::jsonb,

    -- ===== G. Pre-RFP and external market signals =====
    signal_detected                 boolean,
    signal_type                     text,
    signal_title                    text,
    signal_description              text,
    signal_source_url               text,                   -- real URL only when signal_classification = PUBLIC_VERIFIED
    signal_source_name              text,
    signal_published_date           date,
    signal_detected_date            date,
    signal_freshness_days           integer check (signal_freshness_days >= 0),
    signal_relevance_score          integer check (signal_relevance_score between 0 and 100),   -- AI_GENERATED
    signal_confidence_score         integer check (signal_confidence_score between 0 and 100),  -- AI_GENERATED
    potential_product_interest      text,
    procurement_status              text,
    signal_verification_status      text,
    potential_opportunity_reason    text,                   -- AI_GENERATED
    recommended_sales_action        text,                   -- AI_GENERATED
    signal_classification           text,                   -- PUBLIC_VERIFIED | SYNTHETIC

    -- ===== H. Deal blocker =====
    blocker_detected                boolean,
    blocker_category                text,
    blocker_description             text,
    blocker_severity                text,                   -- high | medium | low
    blocker_status                  text,                   -- open | in_progress | resolved
    required_documentation          text,
    suggested_resolution            text,                   -- AI_GENERATED
    blocker_owner                   text,
    blocker_resolution_deadline     date,
    supporting_document_reference   text,

    -- ===== I. Proposal and follow-up (simulated drafts, human approval required) =====
    proposal_generated              boolean,
    proposal_title                  text,
    customer_requirements_summary   text,
    recommended_solution            text,
    recommended_products            text[],
    value_proposition               text,
    proposal_status                 text,                   -- draft | approved | rejected | none
    proposal_draft                  jsonb,
    followup_email_subject          text,
    followup_email_body             text,
    followup_message_status         text,                   -- draft | approved | rejected | none
    next_followup_recommendation    text,

    -- ===== J. Customer handoff (primarily simulated won deals) =====
    handoff_required                boolean,
    handoff_status                  text,
    customer_objectives             text,
    sold_solution                   text,
    implementation_requirements     jsonb,
    delivery_commitments            jsonb,
    handoff_stakeholders            jsonb,
    implementation_risks            jsonb,
    onboarding_checklist            jsonb,
    implementation_timeline         text,
    sales_handoff_summary           text,
    handoff_created_date            date,

    -- ===== K. Source and system metadata =====
    public_source_url               text,
    public_source_name              text,
    public_source_type              text,
    public_source_published_date    date,
    public_source_collected_date    date,
    public_source_verification_status text,                 -- VERIFIED | PARTIALLY_VERIFIED | UNVERIFIED
    record_data_classification      text not null,          -- PUBLIC_VERIFIED | SYNTHETIC | AI_GENERATED (dominant class of the CRM record)
    record_created_at               timestamptz not null default now(),
    record_updated_at               timestamptz not null default now(),

    -- ===== Helper columns (same table, no extra table) =====
    record_segment                  text not null,          -- early_lead | qualified_lead | active_opportunity | stalled_at_risk | lost_inactive | won
    as_of_date                      date not null,          -- fixed demo date used for every day calculation
    field_classification            jsonb not null,         -- per field-group label: PUBLIC_VERIFIED / SYNTHETIC / AI_GENERATED
    product_reference               jsonb,                  -- Pearson product claims with official source URL
    institution_verification        jsonb,                  -- how the official website was checked

    constraint crm_master_segment_chk check (record_segment in
        ('early_lead','qualified_lead','active_opportunity','stalled_at_risk','lost_inactive','won')),
    constraint crm_master_class_chk check (data_classification in ('PUBLIC_VERIFIED','SYNTHETIC','AI_GENERATED')),
    constraint crm_master_record_class_chk check (record_data_classification in ('PUBLIC_VERIFIED','SYNTHETIC','AI_GENERATED')),
    constraint crm_master_risk_chk check (risk_category is null or risk_category in ('high','medium','low')),
    constraint crm_master_priority_chk check (account_priority is null or account_priority in ('high','medium','low')),
    constraint crm_master_signal_class_chk check (signal_classification is null or signal_classification in ('PUBLIC_VERIFIED','SYNTHETIC')),
    constraint crm_master_public_signal_url_chk check (signal_classification is distinct from 'PUBLIC_VERIFIED' or signal_source_url is not null)
);

comment on table revenue_recovery.crm_master is
  'Simulated CRM records about publicly identified institutions. Not actual customers, deals, or contacts of any seller. Hackathon demo data.';

create index if not exists crm_master_segment_idx        on revenue_recovery.crm_master (record_segment);
create index if not exists crm_master_country_idx        on revenue_recovery.crm_master (country);
create index if not exists crm_master_category_idx       on revenue_recovery.crm_master (institution_category);
create index if not exists crm_master_priority_idx       on revenue_recovery.crm_master (account_priority);
create index if not exists crm_master_stage_idx          on revenue_recovery.crm_master (opportunity_stage);
create index if not exists crm_master_deal_status_idx    on revenue_recovery.crm_master (deal_status);
create index if not exists crm_master_risk_cat_idx       on revenue_recovery.crm_master (risk_category);
create index if not exists crm_master_close_date_idx     on revenue_recovery.crm_master (expected_close_date);
create index if not exists crm_master_followup_idx       on revenue_recovery.crm_master (next_followup_date);
create index if not exists crm_master_inactivity_idx     on revenue_recovery.crm_master (inactivity_days);
create index if not exists crm_master_recovery_idx       on revenue_recovery.crm_master (recovery_eligibility);
create index if not exists crm_master_signal_idx         on revenue_recovery.crm_master (signal_detected, signal_classification);
create index if not exists crm_master_blocker_idx        on revenue_recovery.crm_master (blocker_detected, blocker_status);
create index if not exists crm_master_handoff_idx        on revenue_recovery.crm_master (handoff_required, handoff_status);
create index if not exists crm_master_account_name_idx   on revenue_recovery.crm_master (account_name);
create index if not exists crm_master_stakeholders_gin   on revenue_recovery.crm_master using gin (stakeholders);
create index if not exists crm_master_requirements_gin   on revenue_recovery.crm_master using gin (customer_requirements);

-- Existing databases created before uploaded_meetings existed. Safe to re-run.
alter table revenue_recovery.crm_master
    add column if not exists uploaded_meetings jsonb not null default '[]'::jsonb;

comment on column revenue_recovery.crm_master.uploaded_meetings is
  'Append-only array of live-uploaded meetings. Does not replace meeting_transcript or other pre-generated meeting columns. Files live in object storage; this column stores metadata, path, transcript text and extractions.';
