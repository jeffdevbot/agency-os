-- =====================================================================
-- MIGRATION: query_search_term_facts_ranked RPC
-- Purpose:
--   - Push STR grouping / ranking work into Postgres for Claude MCP use
--   - Avoid statement timeouts from fetching and grouping raw STR rows in app code
-- =====================================================================

create or replace function public.query_search_term_facts_ranked(
  p_profile_id uuid,
  p_date_from date,
  p_date_to date,
  p_group_by text,
  p_ad_product text default null,
  p_campaign_type text default null,
  p_keyword_type text default null,
  p_match_type text default null,
  p_campaign_name_contains text default null,
  p_search_term_contains text default null,
  p_keyword_contains text default null,
  p_campaign_names text[] default null,
  p_sort_by text default 'spend',
  p_limit integer default 25
)
returns table (
  group_value text,
  keyword_type_label text,
  spend numeric,
  sales numeric,
  impressions bigint,
  clicks bigint,
  orders bigint,
  acos numeric,
  roas numeric,
  ctr numeric,
  cvr numeric,
  cpc numeric,
  total_group_count bigint,
  total_spend numeric,
  total_sales numeric,
  total_impressions bigint,
  total_clicks bigint,
  total_orders bigint
)
language sql
stable
as $$
  with filtered as (
    select
      report_date,
      campaign_name,
      keyword,
      keyword_type,
      search_term,
      spend,
      sales,
      impressions,
      clicks,
      orders
    from public.search_term_daily_facts
    where profile_id = p_profile_id
      and report_date >= p_date_from
      and report_date <= p_date_to
      and (p_ad_product is null or ad_product = p_ad_product)
      and (p_campaign_type is null or campaign_type = p_campaign_type)
      and (p_keyword_type is null or keyword_type = p_keyword_type)
      and (p_match_type is null or match_type = p_match_type)
      and (p_campaign_name_contains is null or campaign_name ilike '%' || p_campaign_name_contains || '%')
      and (p_search_term_contains is null or search_term ilike '%' || p_search_term_contains || '%')
      and (p_keyword_contains is null or keyword ilike '%' || p_keyword_contains || '%')
      and (
        p_campaign_names is null
        or cardinality(p_campaign_names) = 0
        or campaign_name = any (p_campaign_names)
      )
  ),
  grouped as (
    select
      case p_group_by
        when 'day' then report_date::text
        when 'campaign' then coalesce(nullif(btrim(campaign_name), ''), '(unnamed)')
        when 'keyword' then coalesce(nullif(btrim(keyword), ''), '(blank)')
        when 'keyword_type' then coalesce(nullif(btrim(keyword_type), ''), 'unclassified')
        else coalesce(nullif(btrim(search_term), ''), '(blank)')
      end as group_value,
      case
        when p_group_by = 'keyword'
          then nullif(coalesce(nullif(btrim(keyword_type), ''), 'unclassified'), 'unclassified')
        else null
      end as keyword_type_label,
      sum(spend)::numeric as spend,
      sum(sales)::numeric as sales,
      sum(impressions)::bigint as impressions,
      sum(clicks)::bigint as clicks,
      sum(orders)::bigint as orders
    from filtered
    group by 1, 2
  ),
  ranked as (
    select
      group_value,
      keyword_type_label,
      spend,
      sales,
      impressions,
      clicks,
      orders,
      case when sales > 0 then spend / sales end as acos,
      case when spend > 0 then sales / spend end as roas,
      case when impressions > 0 then clicks::numeric / impressions::numeric end as ctr,
      case when clicks > 0 then orders::numeric / clicks::numeric end as cvr,
      case when clicks > 0 then spend / clicks::numeric end as cpc,
      count(*) over() as total_group_count,
      sum(spend) over() as total_spend,
      sum(sales) over() as total_sales,
      sum(impressions) over() as total_impressions,
      sum(clicks) over() as total_clicks,
      sum(orders) over() as total_orders
    from grouped
  )
  select
    group_value,
    keyword_type_label,
    spend,
    sales,
    impressions,
    clicks,
    orders,
    acos,
    roas,
    ctr,
    cvr,
    cpc,
    total_group_count,
    total_spend,
    total_sales,
    total_impressions,
    total_clicks,
    total_orders
  from ranked
  order by
    case when p_group_by = 'day' then group_value end asc nulls last,
    case when p_group_by <> 'day' and p_sort_by = 'spend' then spend end desc nulls last,
    case when p_group_by <> 'day' and p_sort_by = 'sales' then sales end desc nulls last,
    case when p_group_by <> 'day' and p_sort_by = 'orders' then orders::numeric end desc nulls last,
    case when p_group_by <> 'day' and p_sort_by = 'clicks' then clicks::numeric end desc nulls last,
    case when p_group_by <> 'day' and p_sort_by = 'impressions' then impressions::numeric end desc nulls last,
    case when p_group_by <> 'day' and p_sort_by = 'acos' then acos end desc nulls last,
    case when p_group_by <> 'day' and p_sort_by = 'roas' then roas end desc nulls last,
    case when p_group_by <> 'day' and p_sort_by = 'ctr' then ctr end desc nulls last,
    case when p_group_by <> 'day' and p_sort_by = 'cvr' then cvr end desc nulls last,
    case when p_group_by <> 'day' and p_sort_by = 'cpc' then cpc end desc nulls last,
    group_value asc
  limit greatest(1, least(coalesce(p_limit, 25), 200));
$$;
