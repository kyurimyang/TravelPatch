-- 0006: daily usage counts for the paid calls (LLM, Google Places), kept in the database
-- (decision 2026-11-23). Before this they lived in the API server's memory, and the free host
-- restarts after 15 idle minutes, so every wake-up reset the guests' daily ceiling.
-- Written only by the backend with the service key (backend/app/services/guest_quota.py).
--
-- subject: 'ip:<keyed hash of the address>' for a guest (the raw IP is never stored),
-- 'user:<uuid>' for a signed-in user, 'guests' for all guests together. Rows are per UTC day and
-- are deleted two days later by charge_usage itself (privacy policy: 자동 수집).
create table usage_daily (
  day     date not null,
  kind    text not null check (kind in ('llm', 'places')),
  subject text not null check (char_length(subject) between 1 and 100),
  count   int  not null default 0 check (count >= 0),
  primary key (day, kind, subject)
);
alter table usage_daily enable row level security;
-- No policy: the app's users (anon, authenticated) can neither read nor write it.

-- charge_usage: count one call and return true, or return false without counting, in one
-- transaction. The subject row is locked first, then the total row, always in that order, so
-- concurrent calls (two threads, two servers) never both take the last call and never deadlock.
create or replace function charge_usage(
  p_kind text, p_subject text, p_limit int, p_total_subject text, p_total_limit int
) returns boolean
language plpgsql security definer set search_path = public as $$
declare
  d date := (now() at time zone 'utc')::date;
  c int;
  t int;
begin
  delete from usage_daily where day < d - 1;  -- yesterday is kept for a call made at midnight
  insert into usage_daily(day, kind, subject) values (d, p_kind, p_subject) on conflict do nothing;
  select count into c from usage_daily
    where day = d and kind = p_kind and subject = p_subject for update;
  if c >= p_limit then
    return false;
  end if;
  if p_total_subject is not null then
    insert into usage_daily(day, kind, subject) values (d, p_kind, p_total_subject) on conflict do nothing;
    select count into t from usage_daily
      where day = d and kind = p_kind and subject = p_total_subject for update;
    if t >= p_total_limit then
      return false;
    end if;
    update usage_daily set count = count + 1
      where day = d and kind = p_kind and subject = p_total_subject;
  end if;
  update usage_daily set count = count + 1
    where day = d and kind = p_kind and subject = p_subject;
  return true;
end $$;

-- New functions are executable by everyone (PUBLIC, which includes anon) unless revoked.
revoke execute on function charge_usage(text, text, int, text, int) from public, anon, authenticated;
grant execute on function charge_usage(text, text, int, text, int) to service_role;
