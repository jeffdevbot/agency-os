-- Ensure one generated content row per SKU and allow upsert on sku_id
create unique index if not exists unique_scribe_generated_content_sku on public.scribe_generated_content(sku_id);
