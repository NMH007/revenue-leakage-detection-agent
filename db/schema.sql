-- =====================================================================
-- Revenue Leakage Detection Agent — Database Schema (PostgreSQL / Supabase)
--
-- HOW TO RUN:
--   1. Open your Supabase project
--   2. Left sidebar > SQL Editor > "New query"
--   3. Paste this whole file and click "Run"
-- Running it again is safe (every statement is "if not exists").
-- =====================================================================

-- 1. CONTRACTS --------------------------------------------------------
-- The agreements we PROMISED customers. The Contract Auditor reads these.
create table if not exists contracts (
    id              bigint generated always as identity primary key,
    customer_id     text not null,
    customer_name   text,
    contract_text   text,        -- raw contract language; the LLM reads this
    extracted_terms jsonb,       -- LLM fills this in:
                                 -- {monthly_fee, included_units, overage_rate,
                                 --  contract_end_date, payment_terms}
    created_at      timestamptz default now()
);

-- 2. INVOICES ---------------------------------------------------------
-- What we ACTUALLY billed. Compared against contracts to find gaps.
create table if not exists invoices (
    id              bigint generated always as identity primary key,
    customer_id     text not null,
    amount          numeric(12,2) not null,
    billing_period  text,        -- e.g. '2026-05'
    status          text default 'paid',
    created_at      timestamptz default now()
);

-- 3. USAGE_RECORDS ----------------------------------------------------
-- How much each customer actually USED. Drives the Tier Analyzer.
create table if not exists usage_records (
    id              bigint generated always as identity primary key,
    customer_id     text not null,
    feature_name    text,
    usage_count     numeric(12,2) not null,
    billing_period  text,
    created_at      timestamptz default now()
);

-- 4. LEAKAGE_FINDINGS -------------------------------------------------
-- The OUTPUT. Every agent writes its discoveries here.
create table if not exists leakage_findings (
    id                 bigint generated always as identity primary key,
    finding_type       text not null,   -- 'contract_gap' | 'billing_anomaly' | 'tier_mismatch'
    customer_id        text,
    estimated_loss_usd numeric(12,2) default 0,
    evidence           jsonb,           -- the "proof" behind the number
    detected_at        timestamptz default now(),
    status             text default 'open'   -- 'open' | 'resolved' | 'ignored'
);

-- Indexes make the JOINs and lookups fast.
create index if not exists idx_invoices_customer on invoices(customer_id);
create index if not exists idx_usage_customer    on usage_records(customer_id);
create index if not exists idx_findings_type     on leakage_findings(finding_type);
