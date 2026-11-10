begin;
insert into auth.users (id) values
('00000000-0000-4000-8000-000000000001'),
('00000000-0000-4000-8000-000000000002');
insert into public.bookmarks (user_id,item_id) values
('00000000-0000-4000-8000-000000000001',repeat('a',64)),
('00000000-0000-4000-8000-000000000002',repeat('b',64));
set local role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000001',true);
do $$
begin
  if (select count(*) from public.bookmarks) <> 1 then raise exception 'Cross-user read'; end if;
  begin
    insert into public.bookmarks(user_id,item_id) values ('00000000-0000-4000-8000-000000000002',repeat('c',64));
    raise exception 'Cross-user insertion allowed';
  exception when insufficient_privilege then null;
  end;
  delete from public.bookmarks where user_id='00000000-0000-4000-8000-000000000002';
  if found then raise exception 'Cross-user deletion allowed'; end if;
end $$;
insert into public.bookmarks(user_id,item_id) values ('00000000-0000-4000-8000-000000000001',repeat('d',64));
delete from public.bookmarks where item_id=repeat('d',64);
set local role anon;
do $$
begin
  begin
    perform * from public.bookmarks;
    raise exception 'Anonymous read allowed';
  exception when insufficient_privilege then null;
  end;
end $$;
reset role;
select 'RLS isolation passed' as result;
rollback;
