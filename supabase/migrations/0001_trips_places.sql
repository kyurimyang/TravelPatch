-- 0001: trip list, day plan, and the two Google caches.
-- Times are minutes since midnight (CLAUDE.md 11). Run in Supabase SQL editor.

create table places (
  place_id      text primary key,              -- Google place id
  name          text not null,
  lat           double precision not null,
  lng           double precision not null,
  opening_hours jsonb,                         -- null = unknown (needs_check), never guessed
  fetched_at    timestamptz not null default now()
);

create table travel_times (
  from_place_id text not null references places(place_id),
  to_place_id   text not null references places(place_id),
  mode          text not null check (mode in ('walk', 'transit', 'drive')),
  minutes       int  not null check (minutes >= 0),
  source        text not null check (source in ('api', 'estimate')),
  primary key (from_place_id, to_place_id, mode)
);

create table trips (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references auth.users(id) on delete cascade,
  title          text not null,
  city           text not null,                -- display name, any city in the world
  start_date     date not null,
  end_date       date not null,
  hotel_place_id text references places(place_id),
  created_at     timestamptz not null default now()
);

create table days (
  id           uuid primary key default gen_random_uuid(),
  trip_id      uuid not null references trips(id) on delete cascade,
  date         date not null,
  tz           text not null,                -- IANA zone of the destination, e.g. Europe/Paris
  start_time   int  not null,
  end_deadline int  not null,
  end_place_id text references places(place_id),
  version      int  not null default 1,        -- +1 per confirmed recovery
  unique (trip_id, date)
);

create table activities (
  id               uuid primary key default gen_random_uuid(),
  day_id           uuid not null references days(id) on delete cascade,
  order_index      int  not null,
  title            text not null,
  place_id         text references places(place_id),
  planned_start    int  not null,
  planned_end      int  not null,
  ideal_duration   int  not null,
  min_duration     int  not null,
  category         text not null,
  intent_tags      text[] not null default '{}',
  outdoor          boolean,                    -- null = unknown
  walking_load     int,
  reservation_time int,
  unique (day_id, order_index)
);

create table preferences (
  activity_id     uuid primary key references activities(id) on delete cascade,
  tier            text not null check (tier in ('must', 'nice', 'optional')),
  substitutability real not null default 0 check (substitutability between 0 and 1),
  time_rigidity   text not null check (time_rigidity in ('reserved', 'time_window', 'flexible')),
  source          text not null default 'user' check (source in ('user', 'llm_default'))
);

-- RLS: a user sees only their own trips. Caches are shared; only the backend
-- (service role, which bypasses RLS) writes them.
alter table trips       enable row level security;
alter table days        enable row level security;
alter table activities  enable row level security;
alter table preferences enable row level security;
alter table places      enable row level security;
alter table travel_times enable row level security;

create policy trips_own on trips for all using (user_id = auth.uid());
create policy days_own on days for all using (
  exists (select 1 from trips t where t.id = days.trip_id and t.user_id = auth.uid()));
create policy activities_own on activities for all using (
  exists (select 1 from days d join trips t on t.id = d.trip_id
          where d.id = activities.day_id and t.user_id = auth.uid()));
create policy preferences_own on preferences for all using (
  exists (select 1 from activities a join days d on d.id = a.day_id join trips t on t.id = d.trip_id
          where a.id = preferences.activity_id and t.user_id = auth.uid()));
create policy places_read on places for select using (true);
create policy travel_times_read on travel_times for select using (true);
