begin;
insert into auth.users(id) values ('00000000-0000-4000-8000-000000000011'),('00000000-0000-4000-8000-000000000012');
insert into public.item_reactions values ('00000000-0000-4000-8000-000000000011',repeat('a',64),1),('00000000-0000-4000-8000-000000000012',repeat('a',64),-1);
set local role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000011',true);
do $$begin
  if (select count(*) from public.item_reactions) <> 1 then raise exception 'Cross-account read'; end if;
  begin
    insert into public.item_reactions values ('00000000-0000-4000-8000-000000000012',repeat('b',64),1);
    raise exception 'Cross-account insert';
  exception when insufficient_privilege then null; end;
  begin
    update public.item_reactions set user_id='00000000-0000-4000-8000-000000000012';
    raise exception 'Vote reassigned';
  exception when insufficient_privilege then null; end;
  update public.item_reactions set value=1 where user_id='00000000-0000-4000-8000-000000000012';
  if found then raise exception 'Cross-account update'; end if;
  delete from public.item_reactions where user_id='00000000-0000-4000-8000-000000000012';
  if found then raise exception 'Cross-account delete'; end if;
  begin
    update public.item_reactions set value=0;
    raise exception 'Invalid vote accepted';
  exception when check_violation then null; end;
  begin
    insert into public.item_reactions values ('00000000-0000-4000-8000-000000000011',repeat('a',64),-1);
    raise exception 'Duplicate vote accepted';
  exception when unique_violation then null; end;
end $$;
insert into public.item_reactions values ('00000000-0000-4000-8000-000000000011',repeat('a',64),-1)
on conflict(user_id,item_id) do update set value=excluded.value;
reset role;
do $$begin
  if (select dislikes from public.editorial_feedback where item_id=repeat('a',64)) <> 2 then raise exception 'Bad aggregate'; end if;
end $$;
set local role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000011',true);
delete from public.item_reactions where item_id=repeat('a',64);
set local role anon;
do $$begin
  begin perform * from public.item_reactions; raise exception 'Anonymous read'; exception when insufficient_privilege then null; end;
  begin insert into public.item_reactions values ('00000000-0000-4000-8000-000000000011',repeat('a',64),1); raise exception 'Anonymous vote'; exception when insufficient_privilege then null; end;
  begin perform * from public.editorial_feedback; raise exception 'Public aggregate'; exception when insufficient_privilege then null; end;
end $$;
reset role;
select 'Reaction isolation, replace/retract, constraints and aggregate passed' as result;
rollback;
