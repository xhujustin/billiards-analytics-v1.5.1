-- CueVex mobile social RPC performance layer.
-- Run this in Supabase SQL Editor before redeploying Cloud Run for best latency.

create index if not exists idx_community_posts_user_created_id
on public.community_posts(user_id, created_at desc, id desc);

create index if not exists idx_community_posts_created_id
on public.community_posts(created_at desc, id desc);

create index if not exists idx_community_post_reactions_post_user
on public.community_post_reactions(post_id, user_id);

create index if not exists idx_community_comment_reactions_comment_user
on public.community_comment_reactions(comment_id, user_id);

create index if not exists idx_community_comments_post_created_id
on public.community_comments(post_id, created_at, id);

create index if not exists idx_community_post_bookmarks_user_created_post
on public.community_post_bookmarks(user_id, created_at desc, post_id desc);

create index if not exists idx_user_follows_follower_created
on public.user_follows(follower_user_id, created_at desc);

create index if not exists idx_user_blocks_blocker_blocked
on public.user_blocks(blocker_user_id, blocked_user_id);

create index if not exists idx_user_blocks_blocked_blocker
on public.user_blocks(blocked_user_id, blocker_user_id);

create or replace function public.mobile_hydrated_posts(
  viewer_user_id bigint,
  post_ids bigint[]
)
returns table (
  id bigint,
  user_id bigint,
  author_name text,
  author_avatar_url text,
  badge text,
  title text,
  body text,
  preview_type text,
  recording_id text,
  tone text,
  image_urls jsonb,
  image_transforms jsonb,
  created_at timestamptz,
  updated_at timestamptz,
  likes bigint,
  comments bigint,
  liked_by_me boolean,
  bookmarked_by_me boolean
)
language sql
stable
as $$
  with target_posts as (
    select p.*
    from public.community_posts p
    where p.id = any(post_ids)
      and not exists (
        select 1
        from public.user_blocks b
        where viewer_user_id > 0
          and (
            (b.blocker_user_id = viewer_user_id and b.blocked_user_id = p.user_id)
            or (b.blocker_user_id = p.user_id and b.blocked_user_id = viewer_user_id)
          )
      )
  ),
  reaction_counts as (
    select r.post_id, count(*)::bigint as likes
    from public.community_post_reactions r
    where r.post_id = any(post_ids)
    group by r.post_id
  ),
  comment_counts as (
    select c.post_id, count(*)::bigint as comments
    from public.community_comments c
    where c.post_id = any(post_ids)
    group by c.post_id
  ),
  viewer_reactions as (
    select r.post_id
    from public.community_post_reactions r
    where viewer_user_id > 0
      and r.user_id = viewer_user_id
      and r.post_id = any(post_ids)
  ),
  viewer_bookmarks as (
    select b.post_id
    from public.community_post_bookmarks b
    where viewer_user_id > 0
      and b.user_id = viewer_user_id
      and b.post_id = any(post_ids)
  )
  select
    p.id,
    p.user_id,
    coalesce(nullif(u.username, ''), nullif(mp.display_name, ''), p.author_name, '') as author_name,
    coalesce(nullif(mp.avatar_url, ''), nullif(u.avatar_url, ''), '') as author_avatar_url,
    coalesce(p.badge, '') as badge,
    coalesce(p.title, '') as title,
    coalesce(p.body, '') as body,
    coalesce(p.preview_type, 'pool-table') as preview_type,
    p.recording_id,
    coalesce(p.tone, '') as tone,
    coalesce(p.image_urls, '[]'::jsonb) as image_urls,
    coalesce(p.image_transforms, '[]'::jsonb) as image_transforms,
    p.created_at,
    p.updated_at,
    coalesce(rc.likes, 0)::bigint as likes,
    coalesce(cc.comments, 0)::bigint as comments,
    (vr.post_id is not null) as liked_by_me,
    (vb.post_id is not null) as bookmarked_by_me
  from target_posts p
  left join public.mobile_users u on u.id = p.user_id
  left join public.mobile_profiles mp on mp.user_id = p.user_id
  left join reaction_counts rc on rc.post_id = p.id
  left join comment_counts cc on cc.post_id = p.id
  left join viewer_reactions vr on vr.post_id = p.id
  left join viewer_bookmarks vb on vb.post_id = p.id
  order by array_position(post_ids, p.id);
$$;

create or replace function public.mobile_toggle_post_like(
  viewer_user_id bigint,
  post_id bigint
)
returns table (
  id bigint,
  user_id bigint,
  author_name text,
  author_avatar_url text,
  badge text,
  title text,
  body text,
  preview_type text,
  recording_id text,
  tone text,
  image_urls jsonb,
  image_transforms jsonb,
  created_at timestamptz,
  updated_at timestamptz,
  likes bigint,
  comments bigint,
  liked_by_me boolean,
  bookmarked_by_me boolean
)
language plpgsql
as $$
begin
  perform pg_advisory_xact_lock((post_id % 2147483647)::integer, (viewer_user_id % 2147483647)::integer);

  if not exists (
    select 1
    from public.mobile_hydrated_posts(viewer_user_id, array[post_id])
  ) then
    return;
  end if;

  if exists (
    select 1
    from public.community_post_reactions r
    where r.post_id = post_id and r.user_id = viewer_user_id
  ) then
    delete from public.community_post_reactions r
    where r.post_id = post_id and r.user_id = viewer_user_id;
  else
    insert into public.community_post_reactions(post_id, user_id)
    values (post_id, viewer_user_id)
    on conflict do nothing;
  end if;

  return query
  select *
  from public.mobile_hydrated_posts(viewer_user_id, array[post_id]);
end;
$$;

create or replace function public.mobile_toggle_post_bookmark(
  viewer_user_id bigint,
  post_id bigint
)
returns table (
  id bigint,
  user_id bigint,
  author_name text,
  author_avatar_url text,
  badge text,
  title text,
  body text,
  preview_type text,
  recording_id text,
  tone text,
  image_urls jsonb,
  image_transforms jsonb,
  created_at timestamptz,
  updated_at timestamptz,
  likes bigint,
  comments bigint,
  liked_by_me boolean,
  bookmarked_by_me boolean
)
language plpgsql
as $$
begin
  perform pg_advisory_xact_lock((post_id % 2147483647)::integer, (viewer_user_id % 2147483647)::integer);

  if not exists (
    select 1
    from public.mobile_hydrated_posts(viewer_user_id, array[post_id])
  ) then
    return;
  end if;

  if exists (
    select 1
    from public.community_post_bookmarks b
    where b.post_id = post_id and b.user_id = viewer_user_id
  ) then
    delete from public.community_post_bookmarks b
    where b.post_id = post_id and b.user_id = viewer_user_id;
  else
    insert into public.community_post_bookmarks(post_id, user_id)
    values (post_id, viewer_user_id)
    on conflict do nothing;
  end if;

  return query
  select *
  from public.mobile_hydrated_posts(viewer_user_id, array[post_id]);
end;
$$;

create or replace function public.mobile_user_posts(
  viewer_user_id bigint,
  author_user_id bigint,
  page_limit integer,
  page_offset integer
)
returns table (
  id bigint,
  user_id bigint,
  author_name text,
  author_avatar_url text,
  badge text,
  title text,
  body text,
  preview_type text,
  recording_id text,
  tone text,
  image_urls jsonb,
  image_transforms jsonb,
  created_at timestamptz,
  updated_at timestamptz,
  likes bigint,
  comments bigint,
  liked_by_me boolean,
  bookmarked_by_me boolean,
  total_count bigint
)
language sql
stable
as $$
  with visible as (
    select p.id
    from public.community_posts p
    where p.user_id = author_user_id
      and not exists (
        select 1
        from public.user_blocks b
        where viewer_user_id > 0
          and (
            (b.blocker_user_id = viewer_user_id and b.blocked_user_id = p.user_id)
            or (b.blocker_user_id = p.user_id and b.blocked_user_id = viewer_user_id)
          )
      )
  ),
  paged as (
    select p.id
    from public.community_posts p
    inner join visible v on v.id = p.id
    order by p.created_at desc, p.id desc
    limit page_limit offset page_offset
  ),
  total as (
    select count(*)::bigint as total_count from visible
  )
  select hp.*, total.total_count
  from public.mobile_hydrated_posts(viewer_user_id, array(select id from paged)) hp
  cross join total
  order by hp.created_at desc, hp.id desc;
$$;

create or replace function public.mobile_following_feed(
  viewer_user_id bigint,
  page_limit integer,
  page_offset integer
)
returns table (
  id bigint,
  user_id bigint,
  author_name text,
  author_avatar_url text,
  badge text,
  title text,
  body text,
  preview_type text,
  recording_id text,
  tone text,
  image_urls jsonb,
  image_transforms jsonb,
  created_at timestamptz,
  updated_at timestamptz,
  likes bigint,
  comments bigint,
  liked_by_me boolean,
  bookmarked_by_me boolean,
  total_count bigint
)
language sql
stable
as $$
  with visible as (
    select p.id
    from public.community_posts p
    inner join public.user_follows f on f.following_user_id = p.user_id
    where f.follower_user_id = viewer_user_id
      and not exists (
        select 1
        from public.user_blocks b
        where (b.blocker_user_id = viewer_user_id and b.blocked_user_id = p.user_id)
           or (b.blocker_user_id = p.user_id and b.blocked_user_id = viewer_user_id)
      )
  ),
  paged as (
    select p.id
    from public.community_posts p
    inner join visible v on v.id = p.id
    order by p.created_at desc, p.id desc
    limit page_limit offset page_offset
  ),
  total as (
    select count(*)::bigint as total_count from visible
  )
  select hp.*, total.total_count
  from public.mobile_hydrated_posts(viewer_user_id, array(select id from paged)) hp
  cross join total
  order by hp.created_at desc, hp.id desc;
$$;

create or replace function public.mobile_trending_feed(
  viewer_user_id bigint,
  page_limit integer,
  page_offset integer,
  exclude_ids bigint[] default '{}'
)
returns table (
  id bigint,
  user_id bigint,
  author_name text,
  author_avatar_url text,
  badge text,
  title text,
  body text,
  preview_type text,
  recording_id text,
  tone text,
  image_urls jsonb,
  image_transforms jsonb,
  created_at timestamptz,
  updated_at timestamptz,
  likes bigint,
  comments bigint,
  liked_by_me boolean,
  bookmarked_by_me boolean,
  total_count bigint
)
language sql
stable
as $$
  with recent as (
    select p.id
    from public.community_posts p
    where p.created_at >= now() - interval '3 days'
      and not (p.id = any(exclude_ids))
      and not exists (
        select 1
        from public.user_blocks b
        where viewer_user_id > 0
          and (
            (b.blocker_user_id = viewer_user_id and b.blocked_user_id = p.user_id)
            or (b.blocker_user_id = p.user_id and b.blocked_user_id = viewer_user_id)
          )
      )
  ),
  scored as (
    select
      p.id,
      (coalesce(count(distinct r.user_id), 0) + coalesce(count(distinct c.id), 0) * 2) as score
    from public.community_posts p
    inner join recent re on re.id = p.id
    left join public.community_post_reactions r on r.post_id = p.id
    left join public.community_comments c on c.post_id = p.id
    group by p.id, p.created_at
    order by score desc, p.created_at desc, p.id desc
    limit page_limit offset page_offset
  ),
  total as (
    select count(*)::bigint as total_count from recent
  )
  select hp.*, total.total_count
  from public.mobile_hydrated_posts(viewer_user_id, array(select id from scored)) hp
  cross join total
  left join scored s on s.id = hp.id
  order by s.score desc, hp.created_at desc, hp.id desc;
$$;

create or replace function public.mobile_bookmarked_posts(
  viewer_user_id bigint,
  page_limit integer,
  page_offset integer
)
returns table (
  id bigint,
  user_id bigint,
  author_name text,
  author_avatar_url text,
  badge text,
  title text,
  body text,
  preview_type text,
  recording_id text,
  tone text,
  image_urls jsonb,
  image_transforms jsonb,
  created_at timestamptz,
  updated_at timestamptz,
  likes bigint,
  comments bigint,
  liked_by_me boolean,
  bookmarked_by_me boolean,
  total_count bigint
)
language sql
stable
as $$
  with visible_bookmarks as (
    select b.post_id, b.created_at as bookmarked_at
    from public.community_post_bookmarks b
    inner join public.community_posts p on p.id = b.post_id
    where b.user_id = viewer_user_id
      and not exists (
        select 1
        from public.user_blocks ub
        where (ub.blocker_user_id = viewer_user_id and ub.blocked_user_id = p.user_id)
           or (ub.blocker_user_id = p.user_id and ub.blocked_user_id = viewer_user_id)
      )
  ),
  paged as (
    select post_id
    from visible_bookmarks
    order by bookmarked_at desc, post_id desc
    limit page_limit offset page_offset
  ),
  total as (
    select count(*)::bigint as total_count from visible_bookmarks
  )
  select hp.*, total.total_count
  from public.mobile_hydrated_posts(viewer_user_id, array(select post_id from paged)) hp
  cross join total
  left join visible_bookmarks vb on vb.post_id = hp.id
  order by vb.bookmarked_at desc, hp.id desc;
$$;

create or replace function public.mobile_hydrated_comments(
  viewer_user_id bigint,
  comment_ids bigint[]
)
returns table (
  id bigint,
  post_id bigint,
  user_id bigint,
  author_name text,
  author_avatar_url text,
  author_player_level text,
  body text,
  created_at timestamptz,
  likes bigint,
  liked_by_me boolean
)
language sql
stable
as $$
  with target_comments as (
    select c.*
    from public.community_comments c
    inner join public.community_posts p on p.id = c.post_id
    where c.id = any(comment_ids)
      and not exists (
        select 1
        from public.user_blocks b
        where viewer_user_id > 0
          and (
            (b.blocker_user_id = viewer_user_id and b.blocked_user_id = p.user_id)
            or (b.blocker_user_id = p.user_id and b.blocked_user_id = viewer_user_id)
            or (b.blocker_user_id = viewer_user_id and b.blocked_user_id = c.user_id)
            or (b.blocker_user_id = c.user_id and b.blocked_user_id = viewer_user_id)
          )
      )
  ),
  reaction_counts as (
    select r.comment_id, count(*)::bigint as likes
    from public.community_comment_reactions r
    where r.comment_id = any(comment_ids)
    group by r.comment_id
  ),
  viewer_reactions as (
    select r.comment_id
    from public.community_comment_reactions r
    where viewer_user_id > 0
      and r.user_id = viewer_user_id
      and r.comment_id = any(comment_ids)
  )
  select
    c.id,
    c.post_id,
    c.user_id,
    coalesce(nullif(u.username, ''), nullif(mp.display_name, ''), c.author_name, '') as author_name,
    coalesce(nullif(mp.avatar_url, ''), nullif(u.avatar_url, ''), '') as author_avatar_url,
    case
      when lower(coalesce(nullif(u.username, ''), nullif(mp.display_name, ''), c.author_name, '')) = 'cuevex'
        then '官方帳號'
      else ''
    end as author_player_level,
    coalesce(c.body, '') as body,
    c.created_at,
    coalesce(rc.likes, 0)::bigint as likes,
    (vr.comment_id is not null) as liked_by_me
  from target_comments c
  left join public.mobile_users u on u.id = c.user_id
  left join public.mobile_profiles mp on mp.user_id = c.user_id
  left join reaction_counts rc on rc.comment_id = c.id
  left join viewer_reactions vr on vr.comment_id = c.id
  order by array_position(comment_ids, c.id);
$$;

create or replace function public.mobile_comments_for_post(
  viewer_user_id bigint,
  target_post_id bigint
)
returns table (
  id bigint,
  post_id bigint,
  user_id bigint,
  author_name text,
  author_avatar_url text,
  author_player_level text,
  body text,
  created_at timestamptz,
  likes bigint,
  liked_by_me boolean
)
language sql
stable
as $$
  with visible_post as (
    select p.id
    from public.community_posts p
    where p.id = target_post_id
      and not exists (
        select 1
        from public.user_blocks b
        where viewer_user_id > 0
          and (
            (b.blocker_user_id = viewer_user_id and b.blocked_user_id = p.user_id)
            or (b.blocker_user_id = p.user_id and b.blocked_user_id = viewer_user_id)
          )
      )
  ),
  ordered_comments as (
    select c.id
    from public.community_comments c
    inner join visible_post p on p.id = c.post_id
    where not exists (
      select 1
      from public.user_blocks b
      where viewer_user_id > 0
        and (
          (b.blocker_user_id = viewer_user_id and b.blocked_user_id = c.user_id)
          or (b.blocker_user_id = c.user_id and b.blocked_user_id = viewer_user_id)
        )
    )
    order by c.created_at asc, c.id asc
  )
  select hc.*
  from public.mobile_hydrated_comments(viewer_user_id, array(select id from ordered_comments)) hc
  order by hc.created_at asc, hc.id asc;
$$;

create or replace function public.mobile_create_comment(
  viewer_user_id bigint,
  target_post_id bigint,
  comment_body text
)
returns table (
  comment jsonb,
  post jsonb
)
language plpgsql
as $$
declare
  new_comment_id bigint;
  inserted_comment public.community_comments%rowtype;
  hydrated_comment jsonb;
  hydrated_post jsonb;
begin
  if comment_body is null or length(trim(comment_body)) = 0 then
    return;
  end if;

  if not exists (
    select 1
    from public.mobile_hydrated_posts(viewer_user_id, array[target_post_id])
  ) then
    return;
  end if;

  new_comment_id := (floor(extract(epoch from clock_timestamp()) * 1000000)::bigint + floor(random() * 1000)::bigint);

  insert into public.community_comments(id, post_id, user_id, author_name, body, created_at)
  select
    new_comment_id,
    target_post_id,
    viewer_user_id,
    coalesce(nullif(u.username, ''), ''),
    trim(comment_body),
    now()
  from public.mobile_users u
  where u.id = viewer_user_id
  returning * into inserted_comment;

  if inserted_comment.id is null then
    return;
  end if;

  select to_jsonb(c) into hydrated_comment
  from public.mobile_hydrated_comments(viewer_user_id, array[inserted_comment.id]) c;

  select to_jsonb(p) into hydrated_post
  from public.mobile_hydrated_posts(viewer_user_id, array[target_post_id]) p;

  return query select hydrated_comment, hydrated_post;
end;
$$;

create or replace function public.mobile_toggle_comment_like(
  viewer_user_id bigint,
  target_comment_id bigint
)
returns table (
  id bigint,
  post_id bigint,
  user_id bigint,
  author_name text,
  author_avatar_url text,
  author_player_level text,
  body text,
  created_at timestamptz,
  likes bigint,
  liked_by_me boolean
)
language plpgsql
as $$
begin
  perform pg_advisory_xact_lock((target_comment_id % 2147483647)::integer, (viewer_user_id % 2147483647)::integer);

  if not exists (
    select 1
    from public.mobile_hydrated_comments(viewer_user_id, array[target_comment_id])
  ) then
    return;
  end if;

  if exists (
    select 1
    from public.community_comment_reactions r
    where r.comment_id = target_comment_id and r.user_id = viewer_user_id
  ) then
    delete from public.community_comment_reactions r
    where r.comment_id = target_comment_id and r.user_id = viewer_user_id;
  else
    insert into public.community_comment_reactions(comment_id, user_id)
    values (target_comment_id, viewer_user_id)
    on conflict do nothing;
  end if;

  return query
  select *
  from public.mobile_hydrated_comments(viewer_user_id, array[target_comment_id]);
end;
$$;
