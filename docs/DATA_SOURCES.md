# Alternative catalog sources

Checked October 9, 2026. This preserves the source research. The active deployed
catalog now uses 100 Amazon US 2023 skincare records from the mirror below; see
[catalog workflow](CATALOG.md) and [live deployment](LIVE.md). Other sources remain
research alternatives. No paid data provider was used.

## Amazon Reviews 2023 metadata

- Original research dataset: https://amazon-reviews-2023.github.io/
- Accessible refined mirror: https://huggingface.co/datasets/smartcat/Amazon_Beauty_and_Personal_Care_2023
- Approximately 554,000 records in the mirror, including categories, titles,
  descriptions, image URLs, USD snapshot prices, average ratings and rating counts.
- A live Hugging Face rows request returned 100 records; 45 had nonempty title,
  description, price and images in this preliminary check. Missing/zero prices,
  missing descriptions and unrelated categories need filtering.
- Strongest field match for a 100-product skincare RAG prototype. These are US
  Amazon historical records, not Amazon Mexico or current prices. Source IDs are
  parent ASINs; product links would need to be constructed and labeled accordingly.
- Public/commercial reuse rights for retailer descriptions/images are not verified.
  Availability of a research download does not by itself establish those rights.

## BeautyFeeds free sample

- Dataset: https://huggingface.co/datasets/beautyfeeds/beautyfeeds_sample_data
- Direct CSV download succeeded, saved for inspection under
  `reports/dataset-research/beautyfeeds-sample.csv` (not imported into the store).
- 563 records; 554 had nonempty product name, description, image URL, source URL,
  currency and a positive price. These preliminary checks do not verify image
  availability or category accuracy.
- 124 complete USD records from Ulta and 430 EUR records from Cult Beauty. Only
  73 complete records matched broad skincare keywords in titles/breadcrumbs;
  this sample should not be presented as 100 skincare products.
- Includes ingredient data but no star-rating or review-count columns.
- Provider labels the dataset CC BY-NC 4.0. Attribution and noncommercial use
  restrictions apply; confirm image rights and commercial permission before launch.
- Record dates are in April 2025. Preserve source dates, not download dates, as
  product-price freshness evidence.

## Makeup API

- Documentation: https://makeup-api.herokuapp.com/
- Live endpoint: https://makeup-api.herokuapp.com/api/v1/products.json
- Live unauthenticated request returned 931 records; 854 had nonempty name,
  description, image/product links and positive numeric prices; 340 of those
  included a rating. These are field-completeness counts, not URL-liveness checks.
- Mainly makeup, not a skincare catalog. Some currencies are CAD or missing, so
  never assume every dollar price is USD. Many records are old snapshots.
- Reuse license, image rights, review counts and reliable freshness were not verified.

## Other options

- CrawlFeeds Sephora sample: https://crawlfeeds.com/datasets/sephora-sample-dataset
  Provider lists 340 free records dated June 2021. Preview includes Canadian URLs,
  dollar prices with unclear currency and malformed duplicated image URL prefixes;
  no star-rating column is listed. Requires cleanup and currency/license confirmation.
- The Beauty API: https://thebeautyapi.com/ has an evaluation sandbox at $0/month
  (100 calls), paid API plans from $40/month and a $1,500 full dataset snapshot.
  Ingredient/image coverage is useful, but retail prices and aggregate shopper
  ratings are not confirmed in the displayed schema. Paid recurring access exceeds
  this project's $10 monthly target.

## Recommendation

For closest functional coverage, use filtered Amazon Reviews 2023 metadata for a
local historical demo and resolve public reuse before deployment. For a clearly
labeled noncommercial mixed-beauty demo that can omit ratings, the BeautyFeeds
sample is smaller, directly downloadable, and has an explicit dataset license.
