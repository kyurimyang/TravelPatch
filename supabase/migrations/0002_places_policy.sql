-- 0002: follow Google's caching rules (docs/decisions.md, 2026-11-16).
-- Per Google's policy pages: a place_id may be stored indefinitely, latitude/longitude may be
-- kept for at most 30 consecutive calendar days, and other Google content (names, opening
-- hours, travel times) is fetched when needed and not stored. Run in Supabase SQL editor.
-- Check the current Service Specific Terms before relying on this: the body of that page was
-- not readable when this was written.

alter table places drop column name;
alter table places drop column opening_hours;

-- lat/lng become temporary: the backend nulls them once fetched_at is older than the limit
-- (services/place_cache.purge_expired); the row, and so the place_id, stays.
alter table places alter column lat drop not null;
alter table places alter column lng drop not null;
comment on column places.lat is 'temporary (<= 30 days since fetched_at), then null';
comment on column places.lng is 'temporary (<= 30 days since fetched_at), then null';
comment on column places.fetched_at is 'when lat/lng were fetched; starts the 30-day limit';

-- Google travel times are not stored: the backend asks Routes per request and falls back to
-- the straight-line estimate (services/travel_estimate.py). Policies drop with the table.
drop table travel_times;
