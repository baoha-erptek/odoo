---
source_url: https://developers.gearment.com/api/api.order.v1.vendororderapi
title: Order
crawled_at: 2026-07-05T02:43:47.639168Z
---

[Skip to content](https://developers.gearment.com/api/api.order.v1.vendororderapi#content)
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
      * List Order get ](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder)
[
      * List Order Draft get ](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft)
[
      * Create Order Draft post ](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraft)
[
      * Create Order Draft With Label post ](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraftwithlabel)
[
      * Update Order Draft Line Items patch ](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems)
[
      * Get Order Draft get ](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorderdraft)
[
      * Get Price Quote post ](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote)
[
      * Get Order get ](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorder)
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
[](https://developers.gearment.com/api/api.order.v1.vendororderapi#section/Overview)Overview
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
[](https://developers.gearment.com/api/api.order.v1.vendororderapi#section/Authentication)Authentication
All API requests must be authenticated with an API Key. Unauthorized requests will be rejected.
**How to obtain your API Key**
  1. Navigate to your **Team Settings** inside the Gearment platform.
  2. Click on **Developer Settings**.
  3. Request and generate your **API Key**.


> ⚠️ Important: Keep your API key secure. Do not share it publicly or embed it directly in client-side applications. If your API Key is compromised, immediately revoke it and generate a new one.
### 
[](https://developers.gearment.com/api/api.order.v1.vendororderapi#section/Using-API-Key)Using API Key
Include your API key in the request headers:
> **X-Gearment-Client-Key** : Your_Gearment_Client_Key
> **X-Gearment-Client-Secret** : Your_Gearment_Client_Secret"
### 
[](https://developers.gearment.com/api/api.order.v1.vendororderapi#section/Rate-Limiting)Rate Limiting
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
[](https://developers.gearment.com/api/api.order.v1.vendororderapi#section/Migration-Guide)Migration Guide
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
##  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder)List Order
Copy
  * Copy for LLM
Copy page as Markdown for LLMs
  * [ View as Markdown Open this page as Markdown ](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder.md)
  * [ Open in ChatGPT Get insights from ChatGPT ](https://chat.openai.com/?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.order.v1.vendororderapi%2Fapi.order.v1.vendororderapi.vendorlistorder.md+and+answer+questions+based+on+the+content.)
  * [ Open in Claude Get insights from Claude ](https://claude.ai/new?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.order.v1.vendororderapi%2Fapi.order.v1.vendororderapi.vendorlistorder.md+and+answer+questions+based+on+the+content.)


####  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder/request)Request
List orders with filtering and pagination
GET /api/v3/orders
Use cases:
  * Monitor order status changes
  * Sync orders to your system
  * Generate reports on order volumes


[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder/request/query)Query
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder/t=request&in=query&path=filter.created_at_min)filter.created_at_min _string_ _(date-time)_
ISO 8601 date-time format (e.g., 2024-01-01T00:00:00Z)
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder/t=request&in=query&path=filter.created_methods)filter.created_methods _Array of strings or numbers_ _(created_methods)_
Filter by order creation methods
Items Enum"VENDOR_CREATED_METHOD_SYNC"2"VENDOR_CREATED_METHOD_MANUAL"3"VENDOR_CREATED_METHOD_API"4"VENDOR_CREATED_METHOD_IMPORT"5"VENDOR_CREATED_METHOD_LABEL"6
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder/t=request&in=query&path=filter.order_ids)filter.order_ids _Array of strings_ _(order_ids)_
Filter by specific order IDs
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder/t=request&in=query&path=filter.payment_status)filter.payment_status _Array of strings or numbers_ _(payment_status)_
Filter by payment status (for legacy API compatibility)
Items Enum"VENDOR_ORDER_PAYMENT_STATUS_PENDING"2"VENDOR_ORDER_PAYMENT_STATUS_SUCCESS"3"VENDOR_ORDER_PAYMENT_STATUS_FAILED"4"VENDOR_ORDER_PAYMENT_STATUS_EXPIRED"5"VENDOR_ORDER_PAYMENT_STATUS_SUCCESS_PARTIALLY"6
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder/t=request&in=query&path=filter.statuses)filter.statuses _Array of strings or numbers_ _(statuses)_
Filter by order statuses
Items Enum"VENDOR_ORDER_STATUS_AWAITING_PAYMENT"2"VENDOR_ORDER_STATUS_PAYMENT_FAILED"3"VENDOR_ORDER_STATUS_AWAITING_FULFILLMENT"4"VENDOR_ORDER_STATUS_IN_PRODUCTION"5"VENDOR_ORDER_STATUS_PACKED"6+6 more
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder/t=request&in=query&path=paging.limit)paging.limit _integer_ _(int32)__(limit)_
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder/t=request&in=query&path=paging.page)paging.page _integer_ _(int32)__(page)_
get
/api/v3/orders
  * Production Server
https://apiv2.gearment.com/integration-handler/api/v3/orders
  * Sandbox Server
https://api.gearmentinc.com/integration-handler/api/v3/orders


curl
  * curl
  * JavaScript
  * Node.js
  * Python
  * Java
  * C#
  * PHP
  * Go
  * Ruby
  * R
  * Payload



```
curl -i -X GET \
  'https://apiv2.gearment.com/integration-handler/api/v3/orders?filter.created_at_min=2019-08-24T14%3A15%3A22Z&filter.created_methods=VENDOR_CREATED_METHOD_SYNC&filter.order_ids=ord_abc123xyz&filter.payment_status=VENDOR_ORDER_PAYMENT_STATUS_PENDING&filter.statuses=VENDOR_ORDER_STATUS_AWAITING_PAYMENT&paging.limit=0&paging.page=0'
```

Try it
####  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder/response&c=200)Responses
  1. 200
  2. 400
  3. 401
  4. 403
  5. 404
  6. 500

Expand all
Success
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder/response&c=200/body)Bodyapplication/json
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder/t=response&c=200&path=status)status _string_ _(status)_
Response status: "success" or "error"
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder/t=response&c=200&path=message)message _string_ _(message)_
Human-readable message describing the result
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder/t=response&c=200&path=paging)paging _object_ _(common.type.v1.PagingResponse)_
+Show 4 properties
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorder/t=response&c=200&path=data)data _Array of objects_ _(data)_
List of orders matching the filter criteria Each order includes: ID, status, line items, tracking info, pricing
+Show 33 array properties
Response
  1. 200
  2. 400
  3. 401
  4. 403
  5. 404
  6. 500


application/json

```

{
  "status": "string",
  "message": "string",
  "paging": {
    "total": 0,
    "total_page": 0,
    "page": 0,
    "limit": 0
  },
  "data": [
    { … }
  ]
}

```

#### Feedback documents for customer support
##  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft)List Order Draft
Copy
  * Copy for LLM
Copy page as Markdown for LLMs
  * [ View as Markdown Open this page as Markdown ](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft.md)
  * [ Open in ChatGPT Get insights from ChatGPT ](https://chat.openai.com/?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.order.v1.vendororderapi%2Fapi.order.v1.vendororderapi.vendorlistorderdraft.md+and+answer+questions+based+on+the+content.)
  * [ Open in Claude Get insights from Claude ](https://claude.ai/new?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.order.v1.vendororderapi%2Fapi.order.v1.vendororderapi.vendorlistorderdraft.md+and+answer+questions+based+on+the+content.)


####  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft/request)Request
List order drafts (pending checkout)
GET /api/v3/orders/draft
Use cases:
  * Review drafts before checkout
  * Identify stuck/incomplete orders


[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft/request/query)Query
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft/t=request&in=query&path=filter.created_at_min)filter.created_at_min _string_ _(date-time)_
ISO 8601 date-time format (e.g., 2024-01-01T00:00:00Z)
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft/t=request&in=query&path=filter.created_methods)filter.created_methods _Array of strings or numbers_ _(created_methods)_
Filter by creation methods
Items Enum"VENDOR_CREATED_METHOD_SYNC"2"VENDOR_CREATED_METHOD_MANUAL"3"VENDOR_CREATED_METHOD_API"4"VENDOR_CREATED_METHOD_IMPORT"5"VENDOR_CREATED_METHOD_LABEL"6
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft/t=request&in=query&path=filter.order_ids)filter.order_ids _Array of strings_ _(order_ids)_
Filter by specific order draft IDs
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft/t=request&in=query&path=filter.statuses)filter.statuses _Array of strings or numbers_ _(statuses)_
Filter by draft statuses
Items Enum"VENDOR_ORDER_DRAFT_STATUS_DRAFT"2"VENDOR_ORDER_DRAFT_STATUS_AWAITING_CHECKOUT"3"VENDOR_ORDER_DRAFT_STATUS_CHECKED_OUT"4"VENDOR_ORDER_DRAFT_STATUS_DELETED"5"VENDOR_ORDER_DRAFT_STATUS_ARCHIVED"6
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft/t=request&in=query&path=paging.limit)paging.limit _integer_ _(int32)__(limit)_
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft/t=request&in=query&path=paging.page)paging.page _integer_ _(int32)__(page)_
get
/api/v3/orders/draft
  * Production Server
https://apiv2.gearment.com/integration-handler/api/v3/orders/draft
  * Sandbox Server
https://api.gearmentinc.com/integration-handler/api/v3/orders/draft


curl
  * curl
  * JavaScript
  * Node.js
  * Python
  * Java
  * C#
  * PHP
  * Go
  * Ruby
  * R
  * Payload



```
curl -i -X GET \
  'https://apiv2.gearment.com/integration-handler/api/v3/orders/draft?filter.created_at_min=2019-08-24T14%3A15%3A22Z&filter.created_methods=VENDOR_CREATED_METHOD_SYNC&filter.order_ids=draft_abc123&filter.statuses=VENDOR_ORDER_DRAFT_STATUS_DRAFT&paging.limit=0&paging.page=0'
```

Try it
####  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft/response&c=200)Responses
  1. 200
  2. 400
  3. 401
  4. 403
  5. 404
  6. 500

Expand all
Success
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft/response&c=200/body)Bodyapplication/json
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft/t=response&c=200&path=status)status _string_ _(status)_
Response status: "success" or "error"
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft/t=response&c=200&path=message)message _string_ _(message)_
Human-readable message describing the result
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft/t=response&c=200&path=paging)paging _object_ _(common.type.v1.PagingResponse)_
+Show 4 properties
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorlistorderdraft/t=response&c=200&path=data)data _Array of objects_ _(data)_
List of order drafts matching the filter criteria
+Show 37 array properties
Response
  1. 200
  2. 400
  3. 401
  4. 403
  5. 404
  6. 500


application/json

```

{
  "status": "string",
  "message": "string",
  "paging": {
    "total": 0,
    "total_page": 0,
    "page": 0,
    "limit": 0
  },
  "data": [
    { … }
  ]
}

```

#### Feedback documents for customer support
##  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraft)Create Order Draft
Copy
  * Copy for LLM
Copy page as Markdown for LLMs
  * [ View as Markdown Open this page as Markdown ](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraft.md)
  * [ Open in ChatGPT Get insights from ChatGPT ](https://chat.openai.com/?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.order.v1.vendororderapi%2Fapi.order.v1.vendororderapi.vendorcreateorderdraft.md+and+answer+questions+based+on+the+content.)
  * [ Open in Claude Get insights from Claude ](https://claude.ai/new?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.order.v1.vendororderapi%2Fapi.order.v1.vendororderapi.vendorcreateorderdraft.md+and+answer+questions+based+on+the+content.)


####  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraft/request)RequestExpand all
Create a new order draft
POST /api/v3/orders/draft Content-Type: application/json
Use cases:
  * Place new orders programmatically
  * Bulk order creation
  * Integration with e-commerce platforms


[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraft/request/body)Bodyapplication/jsonrequired
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraft/t=request&path=data)data _object_ _(api.order.v1.VendorOrderDraftManualCreationParams)_
+Show 9 properties
post
/api/v3/orders/draft
  * Production Server
https://apiv2.gearment.com/integration-handler/api/v3/orders/draft
  * Sandbox Server
https://api.gearmentinc.com/integration-handler/api/v3/orders/draft


curl
  * curl
  * JavaScript
  * Node.js
  * Python
  * Java
  * C#
  * PHP
  * Go
  * Ruby
  * R
  * Payload



```
curl -i -X POST \
  https://apiv2.gearment.com/integration-handler/api/v3/orders/draft \
  -H 'Content-Type: application/json' \
  -d '{
    "data": {
      "reference_id": "my-order-12345",
      "platform": "MARKETPLACE_PLATFORM_EBAY",
      "store_id": "store_abc123xyz",
      "agree_at_risk": true,
      "address": {
        "first_name": "John",
        "last_name": "Doe",
        "company": "Acme Corporation",
        "contact_pronoun": "Mr.",
        "street_1": "123 Main Street",
        "street_2": "Apt 4B",
        "state_code": "CA",
        "state_name": "California",
        "city": "Los Angeles",
        "zip_code": "90001",
        "country_code": "US",
        "country_name": "United States",
        "phone_no": "+1-555-123-4567",
        "email": "john.doe@example.com",
        "type": "TYPE_SHIP_FROM"
      },
      "shipping_method": "METHOD_STANDARD",
      "billing_option": {
        "ioss_number": "IM1234567890",
        "ioss_value": {
          "currency_code": "string",
          "units": 0,
          "nanos": 0
        },
        "tax_number": "GB123456789",
        "tax_value": {
          "currency_code": "string",
          "units": 0,
          "nanos": 0
        }
      },
      "gift_message_body": "Happy Birthday! Hope you enjoy this gift. - Sarah",
      "line_items": [
        {
          "variant_id": "variant_abc123",
          "legacy_id": 0,
          "quantity": 2,
          "printing_options": [
            {
              "location_code": "PRINT_LOCATION_CODE_WHOLE",
              "url": "https://example.com/designs/design-12345.png"
            }
          ],
          "barcode_url": "https://example.com/barcodes/item-12345.png"
        }
      ]
    }
  }'
```

Try it
####  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraft/response&c=200)Responses
  1. 200
  2. 400
  3. 401
  4. 403
  5. 404
  6. 500

Expand all
Success
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraft/response&c=200/body)Bodyapplication/json
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraft/t=response&c=200&path=status)status _string_ _(status)_
Response status: "success" or "error"
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraft/t=response&c=200&path=message)message _string_ _(message)_
Human-readable message
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraft/t=response&c=200&path=data)data _object_ _(api.order.v1.VendorOrderDraft.Short)_
+Show 37 properties
Response
  1. 200
  2. 400
  3. 401
  4. 403
  5. 404
  6. 500


application/json

```

{
  "status": "string",
  "message": "string",
  "data": {
    "order_id": "string",
    "team_id": "string",
    "store_id": "string",
    "store_name": "string",
    "reference_id": "string",
    "order_platform": "MARKETPLACE_PLATFORM_EBAY",
    "import_id": "string",
    "pull_id": "string",
    "request_id": "string",
    "created_method": "VENDOR_CREATED_METHOD_SYNC",
    "fulfillment_vendor": "VENDOR_FULFILLMENT_VENDOR_GEARMENT",
    "priority": "VENDOR_FULFILLMENT_PRIORITY_NORMAL",
    "fulfillment_option": { … },
    "shipping_option": { … },
    "billing_option": { … },
    "order_date": "2023-01-15T01:30:15.01Z",
    "status": "VENDOR_ORDER_DRAFT_STATUS_DRAFT",
    "shipping_labels": [ … ],
    "is_label_attached": true,
    "shipping_verification_status": "VENDOR_SHIPPING_VERIFICATION_STATUS_PENDING",
    "product_matching_status": "VENDOR_PRODUCT_MATCHING_STATUS_MATCHED",
    "is_shipping_verification_bypassed": true,
    "is_approved": true,
    "approved_at": "2023-01-15T01:30:15.01Z",
    "origin_draft_id": "string",
    "origin_order_id": "string",
    "addresses": [ … ],
    "line_items": [ … ],
    "gift_messages": [ … ],
    "legacy_external_id": "string",
    "order_total": { … },
    "order_subtotal": { … },
    "order_shipping_fee": { … },
    "order_handle_fee": { … },
    "order_tax": { … },
    "order_fee": { … },
    "order_discount": { … }
  }
}

```

#### Feedback documents for customer support
##  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraftwithlabel)Create Order Draft With Label
Copy
  * Copy for LLM
Copy page as Markdown for LLMs
  * [ View as Markdown Open this page as Markdown ](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraftwithlabel.md)
  * [ Open in ChatGPT Get insights from ChatGPT ](https://chat.openai.com/?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.order.v1.vendororderapi%2Fapi.order.v1.vendororderapi.vendorcreateorderdraftwithlabel.md+and+answer+questions+based+on+the+content.)
  * [ Open in Claude Get insights from Claude ](https://claude.ai/new?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.order.v1.vendororderapi%2Fapi.order.v1.vendororderapi.vendorcreateorderdraftwithlabel.md+and+answer+questions+based+on+the+content.)


####  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraftwithlabel#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraftwithlabel/request)RequestExpand all
Create order draft with pre-purchased shipping label
POST /api/v3/orders/draft/labeled Content-Type: application/json
Use cases:
  * Use your own shipping account
  * Consolidate shipping management


[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraftwithlabel#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraftwithlabel/request/body)Bodyapplication/jsonrequired
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraftwithlabel#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraftwithlabel/t=request&path=data)data _object_ _(api.order.v1.VendorOrderDraftWithLabelCreationParams)_
+Show 7 properties
post
/api/v3/orders/draft/labeled
  * Production Server
https://apiv2.gearment.com/integration-handler/api/v3/orders/draft/labeled
  * Sandbox Server
https://api.gearmentinc.com/integration-handler/api/v3/orders/draft/labeled


curl
  * curl
  * JavaScript
  * Node.js
  * Python
  * Java
  * C#
  * PHP
  * Go
  * Ruby
  * R
  * Payload



```
curl -i -X POST \
  https://apiv2.gearment.com/integration-handler/api/v3/orders/draft/labeled \
  -H 'Content-Type: application/json' \
  -d '{
    "data": {
      "reference_id": "my-order-12345",
      "platform": "MARKETPLACE_PLATFORM_EBAY",
      "store_id": "store_abc123xyz",
      "agree_at_risk": true,
      "shipping_label_urls": [
        "https://example.com/labels/shipping-label-001.pdf"
      ],
      "gift_message_body": "Happy Birthday! Hope you enjoy this gift. - Sarah",
      "line_items": [
        {
          "variant_id": "variant_abc123",
          "legacy_id": 0,
          "quantity": 2,
          "printing_options": [
            {
              "location_code": "PRINT_LOCATION_CODE_WHOLE",
              "url": "https://example.com/designs/design-12345.png"
            }
          ],
          "barcode_url": "https://example.com/barcodes/item-12345.png"
        }
      ]
    }
  }'
```

Try it
####  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraftwithlabel#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraftwithlabel/response&c=200)Responses
  1. 200
  2. 400
  3. 401
  4. 403
  5. 404
  6. 500

Expand all
Success
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraftwithlabel#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraftwithlabel/response&c=200/body)Bodyapplication/json
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraftwithlabel#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraftwithlabel/t=response&c=200&path=status)status _string_ _(status)_
Response status: "success" or "error"
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraftwithlabel#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraftwithlabel/t=response&c=200&path=message)message _string_ _(message)_
Human-readable message describing the result
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraftwithlabel#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorcreateorderdraftwithlabel/t=response&c=200&path=data)data _object_ _(api.order.v1.VendorOrderDraft.Short)_
+Show 37 properties
Response
  1. 200
  2. 400
  3. 401
  4. 403
  5. 404
  6. 500


application/json

```

{
  "status": "string",
  "message": "string",
  "data": {
    "order_id": "string",
    "team_id": "string",
    "store_id": "string",
    "store_name": "string",
    "reference_id": "string",
    "order_platform": "MARKETPLACE_PLATFORM_EBAY",
    "import_id": "string",
    "pull_id": "string",
    "request_id": "string",
    "created_method": "VENDOR_CREATED_METHOD_SYNC",
    "fulfillment_vendor": "VENDOR_FULFILLMENT_VENDOR_GEARMENT",
    "priority": "VENDOR_FULFILLMENT_PRIORITY_NORMAL",
    "fulfillment_option": { … },
    "shipping_option": { … },
    "billing_option": { … },
    "order_date": "2023-01-15T01:30:15.01Z",
    "status": "VENDOR_ORDER_DRAFT_STATUS_DRAFT",
    "shipping_labels": [ … ],
    "is_label_attached": true,
    "shipping_verification_status": "VENDOR_SHIPPING_VERIFICATION_STATUS_PENDING",
    "product_matching_status": "VENDOR_PRODUCT_MATCHING_STATUS_MATCHED",
    "is_shipping_verification_bypassed": true,
    "is_approved": true,
    "approved_at": "2023-01-15T01:30:15.01Z",
    "origin_draft_id": "string",
    "origin_order_id": "string",
    "addresses": [ … ],
    "line_items": [ … ],
    "gift_messages": [ … ],
    "legacy_external_id": "string",
    "order_total": { … },
    "order_subtotal": { … },
    "order_shipping_fee": { … },
    "order_handle_fee": { … },
    "order_tax": { … },
    "order_fee": { … },
    "order_discount": { … }
  }
}

```

#### Feedback documents for customer support
##  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems)Update Order Draft Line Items
Copy
  * Copy for LLM
Copy page as Markdown for LLMs
  * [ View as Markdown Open this page as Markdown ](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems.md)
  * [ Open in ChatGPT Get insights from ChatGPT ](https://chat.openai.com/?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.order.v1.vendororderapi%2Fapi.order.v1.vendororderapi.vendorupdateorderdraftlineitems.md+and+answer+questions+based+on+the+content.)
  * [ Open in Claude Get insights from Claude ](https://claude.ai/new?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.order.v1.vendororderapi%2Fapi.order.v1.vendororderapi.vendorupdateorderdraftlineitems.md+and+answer+questions+based+on+the+content.)


####  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems/request)RequestExpand all
Update line items in an order draft
PATCH /api/v3/orders/draft/line-items Content-Type: application/json
Use cases:
  * Update quantities before checkout
  * Change designs on line items
  * Fix errors in draft orders


[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems/request/body)Bodyapplication/jsonrequired
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems/t=request&path=order_id)order_id _string_ _(order_id)__[ 1 .. 255 ] characters_
Order draft ID to update (format: draft_xxxxx or UUID)
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems/t=request&path=line_items)line_items _Array of objects_ _(line_items)__[ 1 .. 1000 ] items_
Updated line items (can update: quantity, designs, printing options; max 1000 line items per request)
+Show 6 array properties
patch
/api/v3/orders/draft/line-items
  * Production Server
https://apiv2.gearment.com/integration-handler/api/v3/orders/draft/line-items
  * Sandbox Server
https://api.gearmentinc.com/integration-handler/api/v3/orders/draft/line-items


curl
  * curl
  * JavaScript
  * Node.js
  * Python
  * Java
  * C#
  * PHP
  * Go
  * Ruby
  * R
  * Payload



```
curl -i -X PATCH \
  https://apiv2.gearment.com/integration-handler/api/v3/orders/draft/line-items \
  -H 'Content-Type: application/json' \
  -d '{
    "order_id": "string",
    "line_items": [
      {
        "line_item_id": "li_abc123",
        "variant_id": "variant_abc123",
        "legacy_id": 0,
        "quantity": 2,
        "printing_options": [
          {
            "location_code": "PRINT_LOCATION_CODE_WHOLE",
            "url": "https://example.com/designs/design-12345.png"
          }
        ],
        "barcode_url": "https://example.com/barcodes/item-12345.png"
      }
    ]
  }'
```

Try it
####  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems/response&c=200)Responses
  1. 200
  2. 400
  3. 401
  4. 403
  5. 404
  6. 500

Expand all
Success
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems/response&c=200/body)Bodyapplication/json
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems/t=response&c=200&path=status)status _string_ _(status)_
Response status: "success" or "error"
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems/t=response&c=200&path=message)message _string_ _(message)_
Human-readable message
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorupdateorderdraftlineitems/t=response&c=200&path=data)data _object_ _(api.order.v1.VendorUpdateOrderDraftLineItemsResponse.Data)_
+Show property
Response
  1. 200
  2. 400
  3. 401
  4. 403
  5. 404
  6. 500


application/json

```

{
  "status": "string",
  "message": "string",
  "data": {
    "order_id": "string"
  }
}

```

#### Feedback documents for customer support
##  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorderdraft)Get Order Draft
Copy
  * Copy for LLM
Copy page as Markdown for LLMs
  * [ View as Markdown Open this page as Markdown ](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorderdraft.md)
  * [ Open in ChatGPT Get insights from ChatGPT ](https://chat.openai.com/?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.order.v1.vendororderapi%2Fapi.order.v1.vendororderapi.vendorgetorderdraft.md+and+answer+questions+based+on+the+content.)
  * [ Open in Claude Get insights from Claude ](https://claude.ai/new?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.order.v1.vendororderapi%2Fapi.order.v1.vendororderapi.vendorgetorderdraft.md+and+answer+questions+based+on+the+content.)


####  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorderdraft/request)Request
Get details of a specific order draft
GET /api/v3/orders/draft/{order_id}
Use cases:
  * Review draft before checkout
  * Verify pricing and line items


get
/api/v3/orders/draft/{order_id}
  * Production Server
https://apiv2.gearment.com/integration-handler/api/v3/orders/draft/{order_id}
  * Sandbox Server
https://api.gearmentinc.com/integration-handler/api/v3/orders/draft/{order_id}


curl
  * curl
  * JavaScript
  * Node.js
  * Python
  * Java
  * C#
  * PHP
  * Go
  * Ruby
  * R
  * Payload



```
curl -i -X GET \
  'https://apiv2.gearment.com/integration-handler/api/v3/orders/draft/{order_id}'
```

Try it
####  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorderdraft/response&c=200)Responses
  1. 200
  2. 400
  3. 401
  4. 403
  5. 404
  6. 500

Expand all
Success
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorderdraft/response&c=200/body)Bodyapplication/json
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorderdraft/t=response&c=200&path=status)status _string_ _(status)_
Response status: "success" or "error"
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorderdraft/t=response&c=200&path=message)message _string_ _(message)_
Human-readable message
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorderdraft#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorderdraft/t=response&c=200&path=data)data _object_ _(api.order.v1.VendorOrderDraft)_
+Show 38 properties
Response
  1. 200
  2. 400
  3. 401
  4. 403
  5. 404
  6. 500


application/json

```

{
  "status": "string",
  "message": "string",
  "data": {
    "order_id": "string",
    "team_id": "string",
    "store_id": "string",
    "store_name": "string",
    "platform_ref": "string",
    "order_platform": "MARKETPLACE_PLATFORM_EBAY",
    "import_id": "string",
    "pull_id": "string",
    "request_id": "string",
    "created_method": "VENDOR_CREATED_METHOD_SYNC",
    "fulfillment_vendor": "VENDOR_FULFILLMENT_VENDOR_GEARMENT",
    "priority": "VENDOR_FULFILLMENT_PRIORITY_NORMAL",
    "fulfillment_option": { … },
    "shipping_option": { … },
    "billing_option": { … },
    "order_date": "2023-01-15T01:30:15.01Z",
    "status": "VENDOR_ORDER_DRAFT_STATUS_DRAFT",
    "shipping_labels": [ … ],
    "is_label_attached": true,
    "shipping_verification_status": "VENDOR_SHIPPING_VERIFICATION_STATUS_PENDING",
    "product_matching_status": "VENDOR_PRODUCT_MATCHING_STATUS_MATCHED",
    "is_shipping_verification_bypassed": true,
    "is_approved": true,
    "approved_at": "2023-01-15T01:30:15.01Z",
    "origin_draft_id": "string",
    "origin_order_id": "string",
    "addresses": [ … ],
    "line_items": [ … ],
    "gift_messages": [ … ],
    "legacy_external_id": "string",
    "order_subtotal": { … },
    "order_shipping_fee": { … },
    "order_handle_fee": { … },
    "order_tax": { … },
    "order_fee": { … },
    "order_discount": { … },
    "order_total": { … },
    "reference_id": "string"
  }
}

```

#### Feedback documents for customer support
##  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote)Get Price Quote
Copy
  * Copy for LLM
Copy page as Markdown for LLMs
  * [ View as Markdown Open this page as Markdown ](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote.md)
  * [ Open in ChatGPT Get insights from ChatGPT ](https://chat.openai.com/?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.order.v1.vendororderapi%2Fapi.order.v1.vendororderapi.vendorgetpricequote.md+and+answer+questions+based+on+the+content.)
  * [ Open in Claude Get insights from Claude ](https://claude.ai/new?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.order.v1.vendororderapi%2Fapi.order.v1.vendororderapi.vendorgetpricequote.md+and+answer+questions+based+on+the+content.)


####  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote/request)RequestExpand all
Get price quote before creating order
POST /api/v3/orders/price Content-Type: application/json
Response includes:
  * order_total: Total cost
  * order_subtotal: Product costs
  * order_shipping_fee: Shipping cost
  * order_tax: Tax amount


Use cases:
  * Show pricing to customers before checkout
  * Compare shipping methods
  * Calculate profit margins


[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote/request/body)Bodyapplication/jsonrequired
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote/t=request&path=order_platform)order_platform _string_ _(order_platform)_
Platform where the order originates
Enum"""ebay""amazon""shopify""woocommerce""etsy""shopbase""gearment""orderdesk""tiktokshop"+6 more
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote/t=request&path=billing)billing _object_ _(api.order.v1.VendorOrderPriceCalculation.Billing)_
+Show 2 properties
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote/t=request&path=shipping)shipping _object_ _(api.order.v1.VendorOrderPriceCalculation.Shipping)_
+Show 2 properties
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote/t=request&path=line_items)line_items _Array of objects_ _(line_items)_
List of line items to quote (each item requires: variant_id, quantity, print_locations)
+Show 3 array properties
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote/t=request&path=gift_messages)gift_messages _Array of objects_ _(gift_messages)_
Optional gift messages (adds fee if present)
+Show 2 array properties
post
/api/v3/orders/price
  * Production Server
https://apiv2.gearment.com/integration-handler/api/v3/orders/price
  * Sandbox Server
https://api.gearmentinc.com/integration-handler/api/v3/orders/price


curl
  * curl
  * JavaScript
  * Node.js
  * Python
  * Java
  * C#
  * PHP
  * Go
  * Ruby
  * R
  * Payload



```
curl -i -X POST \
  https://apiv2.gearment.com/integration-handler/api/v3/orders/price \
  -H 'Content-Type: application/json' \
  -d '{
    "order_platform": "shopify",
    "billing": {
      "ioss_number": "IM1234567890",
      "tax_number": "GB123456789"
    },
    "shipping": {
      "address": {
        "method": "standard",
        "state_code": "CA",
        "country_code": "US"
      },
      "label": {
        "url": "https://example.com/shipping-label.pdf"
      }
    },
    "line_items": [
      {
        "variant_id": "variant_abc123",
        "quantity": 2,
        "print_locations": [
          "front"
        ]
      }
    ],
    "gift_messages": [
      {
        "gift_message_id": "gift_msg_123",
        "content": "Happy Birthday! Wishing you all the best. - John"
      }
    ]
  }'
```

Try it
####  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote/response&c=200)Responses
  1. 200
  2. 400
  3. 401
  4. 403
  5. 404
  6. 500

Expand all
Success
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote/response&c=200/body)Bodyapplication/json
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote/t=response&c=200&path=status)status _string_ _(status)_
Response status: "success" or "error"
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote/t=response&c=200&path=message)message _string_ _(message)_
Human-readable message
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetpricequote/t=response&c=200&path=data)data _object_ _(api.order.v1.VendorOrderPriceCalculation.OrderPriceQuote)_
+Show 10 properties
Response
  1. 200
  2. 400
  3. 401
  4. 403
  5. 404
  6. 500


application/json

```

{
  "status": "string",
  "message": "string",
  "data": {
    "order_shipping_fee": { … },
    "order_fee": { … },
    "order_tax": { … },
    "order_sub_total": { … },
    "order_total": { … },
    "order_discount": { … },
    "line_items": [ … ],
    "fees": [ … ],
    "order_gift_message_fee": { … },
    "order_handle_fee": { … }
  }
}

```

#### Feedback documents for customer support
##  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorder)Get Order
Copy
  * Copy for LLM
Copy page as Markdown for LLMs
  * [ View as Markdown Open this page as Markdown ](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorder.md)
  * [ Open in ChatGPT Get insights from ChatGPT ](https://chat.openai.com/?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.order.v1.vendororderapi%2Fapi.order.v1.vendororderapi.vendorgetorder.md+and+answer+questions+based+on+the+content.)
  * [ Open in Claude Get insights from Claude ](https://claude.ai/new?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.order.v1.vendororderapi%2Fapi.order.v1.vendororderapi.vendorgetorder.md+and+answer+questions+based+on+the+content.)


####  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorder/request)Request
Get details of a specific order
GET /api/v3/orders/{order_id}
Response includes:
  * Order status and tracking
  * Line items with printing details
  * Shipping information
  * Payment/transaction details


Use cases:
  * Track order fulfillment
  * Get shipping/tracking info
  * Customer support queries


get
/api/v3/orders/{order_id}
  * Production Server
https://apiv2.gearment.com/integration-handler/api/v3/orders/{order_id}
  * Sandbox Server
https://api.gearmentinc.com/integration-handler/api/v3/orders/{order_id}


curl
  * curl
  * JavaScript
  * Node.js
  * Python
  * Java
  * C#
  * PHP
  * Go
  * Ruby
  * R
  * Payload



```
curl -i -X GET \
  'https://apiv2.gearment.com/integration-handler/api/v3/orders/{order_id}'
```

Try it
####  [](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorder/response&c=200)Responses
  1. 200
  2. 400
  3. 401
  4. 403
  5. 404
  6. 500

Expand all
Success
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorder/response&c=200/body)Bodyapplication/json
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorder/t=response&c=200&path=status)status _string_ _(status)_
Response status: "success" or "error"
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorder/t=response&c=200&path=message)message _string_ _(message)_
Human-readable message
[](https://developers.gearment.com/api/api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorder#api.order.v1.vendororderapi/api.order.v1.vendororderapi.vendorgetorder/t=response&c=200&path=data)data _object_ _(api.order.v1.VendorOrder)_
+Show 51 properties
Response
  1. 200
  2. 400
  3. 401
  4. 403
  5. 404
  6. 500


application/json

```

{
  "status": "string",
  "message": "string",
  "data": {
    "order_id": "string",
    "store_id": "string",
    "team_id": "string",
    "created_method": "VENDOR_CREATED_METHOD_SYNC",
    "order_platform": "MARKETPLACE_PLATFORM_EBAY",
    "platform_ref": "string",
    "fulfillment_vendor": "VENDOR_FULFILLMENT_VENDOR_GEARMENT",
    "vendor_ref": "string",
    "priority": "VENDOR_FULFILLMENT_PRIORITY_NORMAL",
    "fulfillment_option": { … },
    "shipping_option": { … },
    "billing_option": { … },
    "shipping_labels": [ … ],
    "order_date": "2023-01-15T01:30:15.01Z",
    "approved_at": "2023-01-15T01:30:15.01Z",
    "paid_at": "2023-01-15T01:30:15.01Z",
    "order_status": "VENDOR_ORDER_STATUS_AWAITING_PAYMENT",
    "primary_package_id": "string",
    "primary_shipment_id": "string",
    "is_label_attached": true,
    "order_subtotal": { … },
    "order_tax": { … },
    "order_fee": { … },
    "order_discount": { … },
    "order_total": { … },
    "order_redeem": { … },
    "paid_total": { … },
    "paid_needed": { … },
    "tracking_no": "string",
    "created_at": "2023-01-15T01:30:15.01Z",
    "updated_at": "2023-01-15T01:30:15.01Z",
    "line_items": [ … ],
    "store_name": "string",
    "addresses": [ … ],
    "stages": [ … ],
    "order_gift_message_fee": { … },
    "order_shipping_fee": { … },
    "order_handle_fee": { … },
    "order_surcharge": { … },
    "order_rush_fee": { … },
    "order_thank_card_fee": { … },
    "order_trackings": [ … ],
    "gift_messages": [ … ],
    "refund_status": "VENDOR_ORDER_REFUND_STATUS_NOT_REQUESTED",
    "cancel_status": "VENDOR_ORDER_CANCEL_STATUS_NOT_REQUESTED",
    "order_priority": "string",
    "transaction_info": { … },
    "cancel_reason": { … },
    "refunded_total": { … },
    "legacy_external_id": "string",
    "reference_id": "string"
  }
}

```

#### Feedback documents for customer support
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
