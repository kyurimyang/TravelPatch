-- 0004: record the sign-up screen's nickname and consent when the user is created
-- (decision 2026-11-19). An email sign-up is not signed in until the mail is confirmed, so the app
-- cannot write profiles/consents itself (RLS); this trigger copies what sign-up sent in the user's
-- metadata. A Google sign-up sends none of it: the consent screen records it after sign-in.
--
-- A failing trigger would fail the sign-up itself, so odd values are skipped, never raised.

create or replace function public.record_signup() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  meta     jsonb := coalesce(new.raw_user_meta_data, '{}');
  nickname text  := left(btrim(coalesce(meta->>'nickname', '')), 20);
begin
  if nickname <> '' then
    insert into profiles(user_id, nickname) values (new.id, nickname)
    on conflict (user_id) do nothing;
  end if;

  -- all three checks must be literally true; anything else records no consent
  if coalesce(meta->>'terms_version', '') <> ''
     and meta->>'age14' = 'true' and meta->>'terms' = 'true' and meta->>'privacy' = 'true' then
    insert into consents(user_id, terms_version, age14, terms, privacy)
    values (new.id, meta->>'terms_version', true, true, true);
  end if;
  return new;
end $$;

-- only the trigger runs it
revoke execute on function public.record_signup() from public, anon, authenticated;

create trigger record_signup after insert on auth.users
  for each row execute function public.record_signup();
