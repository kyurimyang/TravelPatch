-- 0005: the patch picture of an activity (worship, museum, viewpoint, ...), chosen by the LLM while
-- it structures the pasted text (decision 2026-11-22). Picture only: the engine never reads it.
-- null = the category's picture, which is also what every trip saved before this shows.
-- The check is a shape check, not the list: the list lives in backend/app/llm/parser.py
-- (PatchKind), and an unknown kind falls back to the category picture on screen, so adding a
-- kind needs no migration.
alter table activities add column patch text check (patch ~ '^[a-z_]{1,20}$');

-- save_trip and load_trips from 0003, with `patch` added (insert column + load field). Nothing
-- else changed. 0003 is already applied, so the functions are replaced here.
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
                             ideal_duration, category, patch, reservation_time, note, place_query,
                             duration_estimated, dropped, patched, substituted)
      values (day_id, i, it->>'id', it->>'title', it->>'placeId', (it->>'start')::int, (it->>'end')::int,
              (it->>'end')::int - (it->>'start')::int, it->>'category', it->>'patch',
              (it->>'reservationTime')::int,
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
              'id', a.client_key, 'title', a.title, 'category', a.category, 'patch', a.patch,
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
