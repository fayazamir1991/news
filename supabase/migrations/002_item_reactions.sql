-- One current interest vote per account/item. Raw votes remain private.
create table public.item_reactions (
  user_id uuid not null references auth.users(id) on delete cascade,
  item_id text not null check (item_id ~ '^[a-f0-9]{64}$'),
  value smallint not null check (value in (-1, 1)),
  primary key (user_id, item_id)
);
alter table public.item_reactions enable row level security;
revoke all on public.item_reactions from anon, authenticated;
grant select, insert, update, delete on public.item_reactions to authenticated;
grant all on public.item_reactions to service_role;
create policy reactions_read on public.item_reactions for select to authenticated using ((select auth.uid()) = user_id);
create policy reactions_insert on public.item_reactions for insert to authenticated with check ((select auth.uid()) = user_id);
create policy reactions_update on public.item_reactions for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy reactions_delete on public.item_reactions for delete to authenticated using ((select auth.uid()) = user_id);
create index item_reactions_item_idx on public.item_reactions(item_id);
-- Editorial aggregate: only the authorized backend can read it. No user identifiers.
create view public.editorial_feedback with (security_invoker = true) as
select item_id, count(*) filter (where value = 1) as likes,
       count(*) filter (where value = -1) as dislikes
from public.item_reactions group by item_id;
revoke all on public.editorial_feedback from public, anon, authenticated;
grant select on public.editorial_feedback to service_role;
