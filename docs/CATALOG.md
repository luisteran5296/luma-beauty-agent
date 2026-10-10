# Catalog creation and updates

The deployed 100-product skincare selection comes from
[Amazon Beauty & Personal Care 2023](https://huggingface.co/datasets/smartcat/Amazon_Beauty_and_Personal_Care_2023).
Records include external image URLs and aggregate ratings, not written reviews.
Downloaded records/embeddings are excluded from Git. Check upstream terms and
description/image rights for your use; source availability alone is not permission.

## Selection

```powershell
New-Item -ItemType Directory -Force reports | Out-Null
.\.venv\Scripts\python.exe -m scripts.select_amazon_dataset
.\.venv\Scripts\python.exe -m scripts.import_catalog data/amazon-2023/selected.json --require-100
```

The selector pages through the dataset, filters skincare, deduplicates by ASIN,
requires positive USD price/useful text, and HEAD-checks primary images. It writes
exports after each page and stops at 100. Reruns restart scanning; exports are
inspection checkpoints, not a saved resume cursor. Original collectors separately
support resumable queues. Source changes can alter the selection. The initial
selection scanned 1,100 records. Image checks are dated and URLs can later break.

## Fields

| Fields | Requirements |
|---|---|
| `id`, `source`, `source_url` | Retailer-matching ID and HTTPS detail URL |
| `title`, `description` | Required bounded source text |
| `title_en`, `description_en` | English copies, required for cloud publication |
| `brand`, `category`, `features` | Nullable brand, category text, feature array |
| `image_urls` | 1–20 HTTPS URLs |
| `price_source_usd`, `price_mxn` | Positive original price in correct source currency |
| `rating`, `review_count` | Nullable; rating 0–5, nonnegative count |
| `collected_at` | ISO collection/import timestamp |
| `source_snapshot`, `dataset_url` | Original freshness and provenance |

Supported sources: `amazon_us_2023`, `amazon_mx`, `walmart_us`. US prices remain
USD; Amazon Mexico converts at simulated MXN ÷ 18, rounded to cents. An import
timestamp does not make historical prices current. CSV array cells (`features`,
`image_urls`) contain JSON arrays; empty optional fields map to null. JSON input
is a record array. Blank templates are in `data/`.

Exact schema:

```powershell
.\.venv\Scripts\python.exe -c "import json; from beauty.models import Product; print(json.dumps(Product.model_json_schema(), indent=2))"
```

## Import and embed

```powershell
$env:USE_GCLOUD_CREDENTIALS='true'
.\.venv\Scripts\python.exe -m scripts.import_catalog path/to/updated-products.json --require-100 --embed
```

Optional `--translate` fills missing English copies, incurs model charges and
saves a translation checkpoint. Existing English text needs no translation.
Embeddings cache by model/dimension/task and product text. Changed text embeds
again; unchanged text reuses vectors. The pointer switches only after products
and vectors validate. Failure preserves the prior active snapshot.

`data/catalog.json` and `data/retrieval-bundle.json` are compatibility exports.
Immutable versions live under `data/catalogs/`; `data/active-catalog.json` selects
the active pair. Leave pinned catalog/bundle paths unset for automatic refresh.

## Cloud publication and rollback

After verifying the target and authorization:

```powershell
$env:USE_GCLOUD_CREDENTIALS='true'
.\.venv\Scripts\python.exe -m scripts.publish_catalog --approved
```

Both GCS objects upload before Firestore commits versioned products and the active
pointer. Both services refresh within 30 seconds; no agent redeploy is needed.
For rollback, restore the previous pointer's fingerprint and matching two GCS paths
together, then verify health/chat. Retain old snapshots; do not overwrite them.
Forks must adapt [project identifiers](FORKING.md) before publication.

## Scraper limitations

`collect_catalog` and `collect_walmart` use spaced requests, bounded retries and
failure/checkpoint reports. Original attempts were blocked; collectors pause on
challenges and do not bypass them. They are not used for the deployed dataset.
