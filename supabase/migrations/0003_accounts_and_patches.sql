-- 0003: signed-in users keep trips and stitched patches in the normalized tables
-- (decisions 2026-11-18, 2026-11-19). Applied by the Supabase CLI after 0001 and 0002.
--
-- The browser's trip shape (frontend/src/store/trip.tsx) is saved and loaded whole through two
-- functions, save_trip(jsonb, int) and load_trips(), so one save is one transaction.
-- Only place_ids are stored for places (Google terms, 0002): no names, no coordinates.

-- ---------------------------------------------------------------------------------------------
-- 1. Profiles and consents. The nickname can change; consents are a history (decision
--    2026-11-19): each agreement is a new row, never updated, so a later version of the terms
--    does not erase what was agreed before. The current agreement is the latest row.
create table profiles (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  nickname   text not null check (char_length(nickname) between 1 and 20),
  created_at timestamptz not null default now()
);
alter table profiles enable row level security;
create policy profiles_own on profiles for all using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

create table consents (
  id            bigint generated always as identity primary key,
  user_id       uuid not null references auth.users(id) on delete cascade,
  terms_version text not null,
  -- the three required checks of the sign-up screen; a row exists only when all were given
  age14         boolean not null check (age14),
  terms         boolean not null check (terms),
  privacy       boolean not null check (privacy),
  agreed_at     timestamptz not null default now()
);
create index consents_user on consents(user_id, agreed_at desc);
alter table consents enable row level security;
-- insert and read only: no update or delete policy, so rows cannot be changed from the app
create policy consents_insert_own on consents for insert with check (user_id = (select auth.uid()));
create policy consents_read_own on consents for select using (user_id = (select auth.uid()));
-- agreed_at is the server's clock only: the app may not write it (column-level grant)
revoke insert on consents from anon, authenticated;
grant insert (user_id, terms_version, age14, terms, privacy) on consents to authenticated;

-- ---------------------------------------------------------------------------------------------
-- 2. Trips as the app knows them. A trip is saved while it is still being registered, so
--    times may be missing; the server fills tz/start_time when it builds a day for recovery.
alter table trips add column travel_mode text not null default 'transit'
  check (travel_mode in ('transit', 'walk', 'car'));
alter table trips add column hotel_title text;               -- the user's own words, not Google's name
alter table trips add column end_deadline int not null default 1320;
alter table trips add column updated_at timestamptz not null default now();
-- Sync revision (decision 2026-11-19): +1 per save. A save made from an older revision is refused,
-- so one device never silently overwrites another. Not days.version (+1 per confirmed recovery).
alter table trips add column revision int not null default 1;

-- Flights the user entered (never looked up): like the hotel, the user's words + a place_id.
-- buffer null = the server default (60 after landing, 180 before take-off).
alter table trips add column arrival_time     int check (arrival_time between 0 and 1440);
alter table trips add column arrival_place_id text references places(place_id);
alter table trips add column arrival_title    text;
alter table trips add column arrival_buffer   int check (arrival_buffer >= 0);
alter table trips add column departure_time     int check (departure_time between 0 and 1440);
alter table trips add column departure_place_id text references places(place_id);
alter table trips add column departure_title    text;
alter table trips add column departure_buffer   int check (departure_buffer >= 0);
-- a flight is kept only whole (the app saves it once time and airport are both entered)
alter table trips add constraint arrival_whole
  check ((arrival_time is null) = (arrival_place_id is null));
alter table trips add constraint departure_whole
  check ((departure_time is null) = (departure_place_id is null));

alter table days alter column tz drop not null;
alter table days alter column start_time drop not null;
alter table days alter column end_deadline drop not null;
alter table days add column label text;                      -- "1일차" as pasted
alter table days add column issues jsonb not null default '[]'; -- parser issues still to fix

alter table activities alter column planned_start drop not null;
alter table activities alter column planned_end drop not null;
alter table activities alter column ideal_duration drop not null;
alter table activities alter column min_duration drop not null;  -- rule default at build time
alter table activities add column client_key text not null default ''; -- "d0-3": patches refer to it
alter table activities add column note text;
alter table activities add column place_query text;          -- "오모테산도" from "오모테산도 산책"
alter table activities add column duration_estimated boolean not null default false;
alter table activities add column dropped boolean not null default false;
alter table activities add column patched boolean not null default false;
alter table activities add column substituted boolean not null default false;

-- null = the rule default (decided at build time, services/plan_builder.py)
alter table preferences alter column substitutability drop not null;
alter table preferences alter column substitutability drop default;

-- ---------------------------------------------------------------------------------------------
-- 3. Stitched patches: one result row per patch, its change list in recovery_changes
--    (CLAUDE.md invariant 6). Changes name items by client_key, not by FK: activities are
--    rewritten on every save and an FK would cascade the history away.
create table recovery_results (
  id                uuid primary key default gen_random_uuid(),
  trip_id           uuid not null references trips(id) on delete cascade,
  client_key        text not null,                 -- the patch id made in the browser
  day_date          date not null,
  strategy          text not null,
  -- double, not real: 0.9 must come back as 0.9 (real returns 0.8999999762)
  preservation_rate double precision not null check (preservation_rate between 0 and 1),
  event_type        text,                          -- DELAY, WEATHER, ... (null: unknown)
  chips             jsonb not null default '[]',   -- what the user confirmed, as shown
  status            text not null default 'confirmed',
  saved_at          timestamptz not null,
  ord               int not null,                  -- order of stitching (undo takes the last)
  unique (trip_id, client_key)
);

create table recovery_changes (
  id          uuid primary key default gen_random_uuid(),
  result_id   uuid not null references recovery_results(id) on delete cascade,
  ord         int  not null,                     -- order in the patch's change list
  item_key    text not null,
  op          text not null check (op in ('keep', 'move', 'shrink', 'drop', 'substitute', 'extend', 'add')),
  before      jsonb,
  after       jsonb,
  reason_type text,
  reason_data jsonb,
  reason_text text
);

alter table recovery_results enable row level security;
alter table recovery_changes enable row level security;
create policy recovery_results_own on recovery_results for all using (
  exists (select 1 from trips t where t.id = recovery_results.trip_id and t.user_id = (select auth.uid())));
create policy recovery_changes_own on recovery_changes for all using (
  exists (select 1 from recovery_results r join trips t on t.id = r.trip_id
          where r.id = recovery_changes.result_id and t.user_id = (select auth.uid())));

-- ---------------------------------------------------------------------------------------------
-- 4. save_trip(trip, base_revision): replace one trip of the signed-in user, in one transaction.
--    base_revision = the revision the app last loaded or saved; null for a trip never saved.
--    Returns the new revision. Errors, told apart by SQLSTATE in the app:
--      28000 not signed in · 42501 not your trip · PT409 stale (another device saved first)
--      PT410 gone (deleted on another device) · 22023 too large
--    PT409/PT410 are PostgREST's custom codes (HTTP 409/410). Not 40001: the API retries a
--    serialization failure, and a stale save fails again every time, holding the row lock.
--    security definer because it also records place_ids in `places`, which users cannot write;
--    so it checks the caller and the owner itself before touching anything.
create or replace function save_trip(trip jsonb, base_revision int) returns int
language plpgsql security definer set search_path = public as $$
declare
  me      uuid := auth.uid();
  tid     uuid := (trip->>'id')::uuid;
  owner   uuid;
  cur_rev int;
  new_rev int;
  d       jsonb;
  it      jsonb;
  p       jsonb;
  c       jsonb;
  day_id  uuid;
  act_id  uuid;
  res_id  uuid;
  i       int;
  n       int := 0;
begin
  if me is null then raise exception 'not signed in' using errcode = '28000'; end if;

  -- One trip is a few days of a few dozen lines; anything far bigger is not the app.
  if jsonb_array_length(coalesce(trip->'days', '[]')) > 60
     or jsonb_array_length(coalesce(trip->'patches', '[]')) > 500
     or exists (select 1 from jsonb_array_elements(coalesce(trip->'days', '[]')) dd
                where jsonb_array_length(coalesce(dd->'items', '[]')) > 50) then
    raise exception 'trip too large' using errcode = '22023';
  end if;

  -- Lock the trip row: two saves of one trip run one after the other, so both cannot pass the
  -- revision check with the same base and the later one overwrite the earlier.
  select t.user_id, t.revision into owner, cur_rev from trips t where t.id = tid for update;
  if owner is not null and owner <> me then
    raise exception 'not your trip' using errcode = '42501';
  end if;
  if owner is null and base_revision is not null then
    raise exception 'trip is gone' using errcode = 'PT410';
  end if;
  if owner is not null and cur_rev is distinct from base_revision then
    raise exception 'stale revision' using errcode = 'PT409', detail = cur_rev::text;
  end if;
  new_rev := coalesce(cur_rev, 0) + 1;

  -- place ids only (0002): coordinates stay null until the backend caches them
  insert into places(place_id)
    select distinct x from (
      select trip->'hotel'->>'placeId' as x
      union all select trip->'arrival'->'airport'->>'placeId'
      union all select trip->'departure'->'airport'->>'placeId'
      union all
      select a->>'placeId' from jsonb_array_elements(coalesce(trip->'days', '[]')) dd,
                                jsonb_array_elements(coalesce(dd->'items', '[]')) a
    ) ids where x is not null
  on conflict (place_id) do nothing;

  if owner is null then
    -- A new trip. Two devices inserting the same id at once: the second gets a unique
    -- violation (23505), which the app handles like a stale save.
    insert into trips(id, user_id, title, city, start_date, end_date)
    values (tid, me, trip->>'city', trip->>'city', (trip->>'startDate')::date, (trip->>'endDate')::date);
  end if;

  update trips set
    title = trip->>'city', city = trip->>'city',
    start_date = (trip->>'startDate')::date, end_date = (trip->>'endDate')::date,
    hotel_place_id = trip->'hotel'->>'placeId', hotel_title = trip->'hotel'->>'title',
    travel_mode = coalesce(trip->>'travelMode', 'transit'),
    end_deadline = coalesce((trip->>'endDeadline')::int, 1320),
    arrival_time = (trip->'arrival'->>'time')::int,
    arrival_place_id = trip->'arrival'->'airport'->>'placeId',
    arrival_title = trip->'arrival'->'airport'->>'title',
    arrival_buffer = (trip->'arrival'->>'bufferMinutes')::int,
    departure_time = (trip->'departure'->>'time')::int,
    departure_place_id = trip->'departure'->'airport'->>'placeId',
    departure_title = trip->'departure'->'airport'->>'title',
    departure_buffer = (trip->'departure'->>'bufferMinutes')::int,
    revision = new_rev, updated_at = now()
  where id = tid;

  delete from days where days.trip_id = tid;                  -- cascades to activities, preferences
  delete from recovery_results where recovery_results.trip_id = tid;  -- cascades to changes

  for d in select * from jsonb_array_elements(coalesce(trip->'days', '[]')) loop
    insert into days(trip_id, date, label, issues)
    values (tid, (d->>'date')::date, d->>'label', coalesce(d->'issues', '[]'))
    returning id into day_id;
    i := 0;
    for it in select * from jsonb_array_elements(coalesce(d->'items', '[]')) loop
      insert into activities(day_id, order_index, client_key, title, place_id, planned_start, planned_end,
                             ideal_duration, category, reservation_time, note, place_query,
                             duration_estimated, dropped, patched, substituted)
      values (day_id, i, it->>'id', it->>'title', it->>'placeId', (it->>'start')::int, (it->>'end')::int,
              (it->>'end')::int - (it->>'start')::int, it->>'category', (it->>'reservationTime')::int,
              it->>'note', it->>'placeQuery', coalesce((it->>'durationEstimated')::boolean, false),
              coalesce((it->>'dropped')::boolean, false), coalesce((it->>'patched')::boolean, false),
              coalesce((it->>'substituted')::boolean, false))
      returning id into act_id;
      insert into preferences(activity_id, tier, time_rigidity, source)
      values (act_id, it->>'tier',
              case when it->>'reservationTime' is not null then 'reserved' else 'flexible' end, 'user');
      i := i + 1;
    end loop;
  end loop;

  for p in select * from jsonb_array_elements(coalesce(trip->'patches', '[]')) loop
    insert into recovery_results(trip_id, client_key, day_date, strategy, preservation_rate,
                                 event_type, chips, saved_at, ord)
    values (tid, p->>'id', (p->>'date')::date, p->>'strategy', (p->>'preservationRate')::double precision,
            p->>'eventType', coalesce(p->'chips', '[]'), (p->>'savedAt')::timestamptz, n)
    returning id into res_id;
    n := n + 1;
    i := 0;
    for c in select * from jsonb_array_elements(coalesce(p->'changes', '[]')) loop
      insert into recovery_changes(result_id, ord, item_key, op, before, after)
      values (res_id, i, c->>'itemId', c->>'op', c->'before', c->'after');
      i := i + 1;
    end loop;
  end loop;
  return new_rev;
end $$;

-- ---------------------------------------------------------------------------------------------
-- 5. load_trips(): every trip of the signed-in user, in the browser's shape plus `revision`.
--    security invoker: RLS decides what is returned.
create or replace function load_trips() returns jsonb
language sql stable security invoker set search_path = public as $$
  select coalesce(jsonb_agg(
    jsonb_build_object(
      'id', t.id, 'revision', t.revision, 'city', t.city, 'startDate', t.start_date, 'endDate', t.end_date,
      'hotel', case when t.hotel_place_id is null then null
                    else jsonb_build_object('title', coalesce(t.hotel_title, ''), 'placeId', t.hotel_place_id) end,
      'travelMode', t.travel_mode, 'endDeadline', t.end_deadline,
      'arrival', case when t.arrival_time is null then null else jsonb_build_object(
          'time', t.arrival_time, 'bufferMinutes', t.arrival_buffer,
          'airport', jsonb_build_object('title', coalesce(t.arrival_title, ''), 'placeId', t.arrival_place_id)) end,
      'departure', case when t.departure_time is null then null else jsonb_build_object(
          'time', t.departure_time, 'bufferMinutes', t.departure_buffer,
          'airport', jsonb_build_object('title', coalesce(t.departure_title, ''), 'placeId', t.departure_place_id)) end,
      'days', coalesce((
        select jsonb_agg(jsonb_build_object(
          'date', d.date, 'label', d.label, 'issues', d.issues,
          'items', coalesce((
            select jsonb_agg(jsonb_build_object(
              'id', a.client_key, 'title', a.title, 'category', a.category,
              'start', a.planned_start, 'end', a.planned_end,
              'durationEstimated', a.duration_estimated, 'reservationTime', a.reservation_time,
              'note', a.note, 'placeQuery', a.place_query, 'placeId', a.place_id, 'tier', pr.tier,
              'dropped', a.dropped, 'patched', a.patched, 'substituted', a.substituted
            ) order by a.order_index)
            from activities a join preferences pr on pr.activity_id = a.id
            where a.day_id = d.id), '[]'::jsonb)
        ) order by d.date)
        from days d where d.trip_id = t.id), '[]'::jsonb),
      'patches', coalesce((
        select jsonb_agg(jsonb_build_object(
          'id', r.client_key, 'date', r.day_date, 'savedAt', r.saved_at, 'strategy', r.strategy,
          'preservationRate', r.preservation_rate, 'chips', r.chips, 'eventType', r.event_type,
          'changes', coalesce((
            select jsonb_agg(jsonb_build_object('itemId', c.item_key, 'op', c.op,
                                                'before', c.before, 'after', c.after) order by c.ord)
            from recovery_changes c where c.result_id = r.id), '[]'::jsonb)
        ) order by r.ord)
        from recovery_results r where r.trip_id = t.id), '[]'::jsonb)
    ) order by t.created_at, t.id), '[]'::jsonb)
  from trips t where t.user_id = auth.uid();
$$;

-- New functions are executable by everyone (PUBLIC, which includes anon) unless revoked.
revoke execute on function save_trip(jsonb, int) from public, anon;
revoke execute on function load_trips() from public, anon;
grant execute on function save_trip(jsonb, int) to authenticated;
grant execute on function load_trips() to authenticated;

-- ---------------------------------------------------------------------------------------------
-- 6. The 0001 policies with auth.uid() evaluated once per query, not once per row (Supabase
--    advisor auth_rls_initplan). Same rules; 0001 is already applied in production, so it is
--    changed here rather than edited.
alter policy trips_own on trips using (user_id = (select auth.uid()));
alter policy days_own on days using (
  exists (select 1 from trips t where t.id = days.trip_id and t.user_id = (select auth.uid())));
alter policy activities_own on activities using (
  exists (select 1 from days d join trips t on t.id = d.trip_id
          where d.id = activities.day_id and t.user_id = (select auth.uid())));
alter policy preferences_own on preferences using (
  exists (select 1 from activities a join days d on d.id = a.day_id join trips t on t.id = d.trip_id
          where a.id = preferences.activity_id and t.user_id = (select auth.uid())));
