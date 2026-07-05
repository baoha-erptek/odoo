---
source_url: https://developers.gearment.com/api/section/overview
title: Overview
crawled_at: 2026-07-05T02:43:44.659741Z
---

[Skip to content](https://developers.gearment.com/api/section/overview#content)
[
  * ![](https://developers.gearment.com/assets/gearment-icon.e336162cac52d932ae6af2c4a547b417045597aac01be12da506d1834ec77cd3.9c1bb791.png)Gearment API ](https://developers.gearment.com/api)
[
    * Overview](https://developers.gearment.com/api/section/overview)
[
    * Authentication](https://developers.gearment.com/api/section/authentication)
[
    * Using API Key](https://developers.gearment.com/api/section/using-api-key)
[
    * Rate Limiting](https://developers.gearment.com/api/section/rate-limiting)
[
    * Migration Guide](https://developers.gearment.com/api/section/migration-guide)
[
    * Webhook](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi)
[
    * Order](https://developers.gearment.com/api/api.order.v1.vendororderapi)
[
    * Catalog](https://developers.gearment.com/api/api.catalog.v1.vendorcatalogapi)
[
  * ![](https://developers.gearment.com/assets/gearment-icon.e336162cac52d932ae6af2c4a547b417045597aac01be12da506d1834ec77cd3.9c1bb791.png)Gearment Webhook ](https://developers.gearment.com/webhook)


# Gearment API integration (v3.0.0)
Copy
  * Copy for LLM
Copy page as Markdown for LLMs
  * [ View as Markdown Open this page as Markdown ](https://developers.gearment.com/api.md)
  * [ Open in ChatGPT Get insights from ChatGPT ](https://chat.openai.com/?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi.md+and+answer+questions+based+on+the+content.)
  * [ Open in Claude Get insights from Claude ](https://claude.ai/new?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi.md+and+answer+questions+based+on+the+content.)


[Find out more about Gearment API v3](https://gearment.com/integration/api-docs.html)
### 
[](https://developers.gearment.com/api/section/overview#section/Overview)Overview
Welcome to the Gearment Print-On-Demand (POD) Seller API! This API enables seamless integration between your stores, applications, and the Gearment platform. With our API, you can:
  * Manage products and variants
  * Sync inventory
  * Create and manage orders
  * Track fulfillment status


This documentation will guide you through authentication, rate limits, and how to start using the API.
> **Production API v3 URL:** https://apiv2.gearment.com/integration-handler
> **Sandbox API v3 URL:** https://api.gearmentinc.com/integration-handler
> **Need to use API v2**  
>  👉 [View API v2 Documentation here](https://api.gearment.com)
### 
[](https://developers.gearment.com/api/section/overview#section/Authentication)Authentication
All API requests must be authenticated with an API Key. Unauthorized requests will be rejected.
**How to obtain your API Key**
  1. Navigate to your **Team Settings** inside the Gearment platform.
  2. Click on **Developer Settings**.
  3. Request and generate your **API Key**.


> ⚠️ Important: Keep your API key secure. Do not share it publicly or embed it directly in client-side applications. If your API Key is compromised, immediately revoke it and generate a new one.
### 
[](https://developers.gearment.com/api/section/overview#section/Using-API-Key)Using API Key
Include your API key in the request headers:
> **X-Gearment-Client-Key** : Your_Gearment_Client_Key
> **X-Gearment-Client-Secret** : Your_Gearment_Client_Secret"
### 
[](https://developers.gearment.com/api/section/overview#section/Rate-Limiting)Rate Limiting
To ensure stable service for all users, the Gearment API enforces rate limiting.  
| Rate Limit Type  | Value  |  
| --- | --- |  
| Requests  | 100 requests per 10 seconds, Block for 1 minute  |  
| Retry-After  | If exceeded, Retry-After header will indicate when you can retry  |  
If you exceed the rate limit, the API will respond with:

```
json{
  "error": {
    "code": 429,
    "message": "Rate limit exceeded. Please retry later."
  }
}
```

**Best Practices:**
  * Implement exponential backoff retries for 429 errors.
  * Monitor your API usage.
  * Optimize your integrations to avoid unnecessary requests (e.g., batch updates when possible).


### 
[](https://developers.gearment.com/api/section/overview#section/Migration-Guide)Migration Guide
**🚀 Migration Guide: Moving from[v1/v2](https://api.gearment.com) to [Next App v3 API/Webhook](https://developers.gearment.com/)**
We’ve upgraded our platform to the new [**Next App**](https://dash.gearment.com), which provides [**API v3**](https://developers.gearment.com/), delivering better performance, scalability, and new features.
Good news:  
✅ **Backward compatibility is preserved.**  
Your existing integrations using [**API v1/v2**](https://api.gearment.com) and **Webhook v1/v2** will continue to work **out of the box** without changes.  
✅ You can switch to the new APIs at your own pace.
* * *
**1. What stays the same**
  * Your current API calls [**v1/v2**](https://api.gearment.com) and boundWebhooks will continue to work exactly as before.
  * We have a **compatibility layer** that routes those calls to the new system.
  * **No immediate action is required** for existing apps.


* * *
**2. API Endpoints Overview**  
| Version  | Base URL  | Sandbox  | Notes  |  
| --- | --- | --- | --- |  
| v1/v2  | `https://api.gearment.com`  | N/A  | v1/v2 API, still supported via compatibility layer  |  
| v3  | `https://apiv2.gearment.com/integration-handler`  | `https://api.gearmentinc.com/integration-handler`  | Next App API (new API features)  |  
* * *
**3. What’s new in[API v3](https://developers.gearment.com/)**
  * Modernized endpoints for improved queries and faster responses.
  * Consistent authentication and more detailed error handling.
  * Access to **new features** and data models not available in v1/v2.
  * Enhanced developer experience with updated documentation and examples.


**Example API v3 Request:**
  * Now you can filter product variants with more criterions, e.g.: look for product variants have product_id G5000, variant_id in GM0002003147/GM0002005986, with size 3XL, and color Daisy.



```
curl -i -X GET \
  -H "X-Gearment-Client-Key: xxx" \
  -H "X-Gearment-Client-Secret: xxxxxx" \
  'https://apiv2.gearment.com/integration-handler/api/v3/catalog/variants/stock?filter.product_ids=G5000&filter.variant_ids=GM0002003147&filter.variant_id=GM0002005986&filter.sizes=3XL&filter.color_codes=daisy&filter.stock_labels=VENDOR_CATALOG_VARIANT_STOCK_LABEL_IN_STOCK&paging.page=1&paging.limit=100'
```

  * You can also list/delete webhooks via [APIs](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi).


* * *
**4. Webhooks in v3** Modified payload for webhooks
👉 Configure your webhooks in the [Developer Settings](https://dash.gearment.com/pod/teams/developer-settings/webhooks).
**Example Shipping Address Verified Webhook Payload:**
  * v1/v2:



```
{
  "type": "shipping_address_verified",
  "data": {
    "gearment_ord_id": "ORD123456789",
    "gearment_ord_name": "#10001",
    "ord_status": "pending",
    "verify_address": "verified",
    "order_id": "EXT-1234567"
  }
}
```

  * v3:



```
{
  "type": "shipping_address_verified",
  "order": {
    "gearment_id": "ORD123456789",
    "gearment_name": "#10001",
    "vendor_id": "EXT-1234567",
    "verify_address": "verified",
    "ord_status": "pending"
  }
}
```

* * *
**5. Migration Path** If you’re ready to explore [**API v3**](https://developers.gearment.com/), follow these steps:
  1. Take a glance at our **API v3 Documentation** : [👉 Get Started Here](https://developers.gearment.com/)
  2. Visit [Developer Settings](https://dash.gearment.com/pod/teams/developer-settings/api-credentials) to generate new API credentials for [API/Webhooks v3](https://developers.gearment.com/).
  3. Review the updated endpoint list and request/response formats.
  4. Update your integration to start using v3 endpoints at your own pace.


* * *
**6. Recommendations**
  * **Short-term:** Continue running on v1/v2 without changes if everything works.
  * **Medium-term:** Start adopting v3 for new development to take advantage of improvements.
  * **Long-term:** Plan a full migration, as v1/v2 may be deprecated in the future _(deprecation timelines will be communicated well in advance)._


* * *
**7. Support** Need help migrating?
  * 📖 [Documentation](https://developers.gearment.com/)
  * 💬 Contact our support team


Download OpenAPI description
[api.json](https://developers.gearment.com/_bundle/api.json?download)[](https://developers.gearment.com/_bundle/api.json?download)
[api.yaml](https://developers.gearment.com/_bundle/api.yaml?download)[](https://developers.gearment.com/_bundle/api.yaml?download)
Overview
Support Integration
integration@gearment.com
[Terms of Service](https://gearment.com/integration/api-terms-of-service.html)
Languages
Servers
Production Server
https://apiv2.gearment.com/integration-handler/
Sandbox Server
https://api.gearmentinc.com/integration-handler/
##  [](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi)Webhook
Copy
  * Copy for LLM
Copy page as Markdown for LLMs
  * [ View as Markdown Open this page as Markdown ](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi.md)
  * [ Open in ChatGPT Get insights from ChatGPT ](https://chat.openai.com/?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.webhook.v1.vendorwebhookapi.md+and+answer+questions+based+on+the+content.)
  * [ Open in Claude Get insights from Claude ](https://claude.ai/new?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.webhook.v1.vendorwebhookapi.md+and+answer+questions+based+on+the+content.)


VendorWebhookAPI provides webhook management for real-time event notifications. Register webhooks to receive automated notifications when orders are completed, cancelled, or tracking is updated.
Base URL: https://apiv2.gearment.com/integration-handler Authentication: API Key (header: X-API-Key, X-API-Secret)
Operations
get
/api/v3/webhooks
post
/api/v3/webhooks
delete
/api/v3/webhooks/{webhook_id}
+ Show
##  [](https://developers.gearment.com/api/api.order.v1.vendororderapi)Order
Copy
  * Copy for LLM
Copy page as Markdown for LLMs
  * [ View as Markdown Open this page as Markdown ](https://developers.gearment.com/api/api.order.v1.vendororderapi.md)
  * [ Open in ChatGPT Get insights from ChatGPT ](https://chat.openai.com/?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.order.v1.vendororderapi.md+and+answer+questions+based+on+the+content.)
  * [ Open in Claude Get insights from Claude ](https://claude.ai/new?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.order.v1.vendororderapi.md+and+answer+questions+based+on+the+content.)


VendorOrderAPI provides comprehensive order management capabilities for vendors. All endpoints require authentication via X-API-Key and X-API-Secret headers.
Base URL: https://apiv2.gearment.com/integration-handler Authentication: API Key (header: X-API-Key, X-API-Secret)
Operations
get
/api/v3/orders
get
/api/v3/orders/draft
post
/api/v3/orders/draft
post
/api/v3/orders/draft/labeled
patch
/api/v3/orders/draft/line-items
get
/api/v3/orders/draft/{order_id}
post
/api/v3/orders/price
get
/api/v3/orders/{order_id}
+ Show
##  [](https://developers.gearment.com/api/api.catalog.v1.vendorcatalogapi)Catalog
Copy
  * Copy for LLM
Copy page as Markdown for LLMs
  * [ View as Markdown Open this page as Markdown ](https://developers.gearment.com/api/api.catalog.v1.vendorcatalogapi.md)
  * [ Open in ChatGPT Get insights from ChatGPT ](https://chat.openai.com/?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.catalog.v1.vendorcatalogapi.md+and+answer+questions+based+on+the+content.)
  * [ Open in Claude Get insights from Claude ](https://claude.ai/new?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.catalog.v1.vendorcatalogapi.md+and+answer+questions+based+on+the+content.)


VendorCatalogAPI provides access to product catalog and inventory management. Use these endpoints to browse available products, check stock status, and get product details.
Base URL: https://apiv2.gearment.com/integration-handler Authentication: API Key (header: X-API-Key, X-API-Secret)
Operations
get
/api/v3/catalog
get
/api/v3/catalog/variants
get
/api/v3/catalog/variants/stock
+ Show
