from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlparse
import re
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class Product(BaseModel):
    id: str = Field(pattern=r'^(?:[A-Z0-9]{10}|walmart-[0-9]{1,20})$')
    source: Literal['amazon_mx', 'amazon_us_2023', 'walmart_us'] = 'amazon_mx'
    dataset_url: str | None = None
    source_snapshot: str | None = None
    title: str = Field(min_length=2, max_length=500)
    brand: str | None = None
    description: str = Field(min_length=10, max_length=12000)
    description_en: str | None = Field(default=None, max_length=12000)
    title_en: str | None = Field(default=None, max_length=500)
    features: list[str] = Field(default_factory=list)
    category: str = 'Beauty'
    image_urls: list[str] = Field(min_length=1, max_length=20)
    source_url: str
    price_mxn: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    price_source_usd: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    collected_at: datetime

    @field_validator('image_urls')
    @classmethod
    def images_https(cls, values):
        if any(urlparse(u).scheme != 'https' or not urlparse(u).hostname for u in values):
            raise ValueError('Image URLs must use HTTPS')
        return values

    @model_validator(mode='after')
    def source_matches(self):
        u = urlparse(self.source_url)
        if self.source in ('amazon_mx', 'amazon_us_2023'):
            hosts = ('amazon.com.mx', 'www.amazon.com.mx') if self.source == 'amazon_mx' else ('amazon.com', 'www.amazon.com')
            currency_valid = (self.price_mxn is not None and self.price_source_usd is None) if self.source == 'amazon_mx' else (self.price_source_usd is not None and self.price_mxn is None)
            valid = (re.fullmatch(r'[A-Z0-9]{10}', self.id) and
                     u.hostname in hosts and
                     re.fullmatch(r'/dp/' + self.id + r'/?', u.path) and
                     currency_valid)
        else:
            valid = (self.id.startswith('walmart-') and
                     u.hostname in ('walmart.com', 'www.walmart.com') and
                     re.fullmatch(r'/ip/(?:[^/]+/)?' + self.id.removeprefix('walmart-') + r'/?', u.path) and
                     self.price_source_usd is not None and self.price_mxn is None)
        if u.scheme != 'https' or not valid:
            raise ValueError('Source URL, product ID and original currency must match the selected retailer')
        return self

    @property
    def price_usd(self) -> Decimal:
        amount = self.price_mxn / Decimal(18) if self.source == 'amazon_mx' else self.price_source_usd
        return amount.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

    def public(self) -> dict:
        data = self.model_dump(mode='json')
        data.update(title=self.title_en or self.title, description=self.description_en or self.description,
                    price_usd=float(self.price_usd), price_mxn=float(self.price_mxn) if self.price_mxn is not None else None)
        return data

    def document(self) -> str:
        return f'{self.title_en or self.title}\nBrand: {self.brand or "unknown"}\nCategory: {self.category}\n{self.description_en or self.description}'
