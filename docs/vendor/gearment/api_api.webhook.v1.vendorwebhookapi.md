---
source_url: https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi
title: Webhook
crawled_at: 2026-07-05T02:43:50.084330Z
---

[Skip to content](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi#content)
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
      * List Webhook get ](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook)
[
      * Create Webhook post ](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook)
[
      * Delete Webhook delete ](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendordeletewebhook)
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
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi#section/Overview)Overview
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
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi#section/Authentication)Authentication
All API requests must be authenticated with an API Key. Unauthorized requests will be rejected.
**How to obtain your API Key**
  1. Navigate to your **Team Settings** inside the Gearment platform.
  2. Click on **Developer Settings**.
  3. Request and generate your **API Key**.


> ⚠️ Important: Keep your API key secure. Do not share it publicly or embed it directly in client-side applications. If your API Key is compromised, immediately revoke it and generate a new one.
### 
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi#section/Using-API-Key)Using API Key
Include your API key in the request headers:
> **X-Gearment-Client-Key** : Your_Gearment_Client_Key
> **X-Gearment-Client-Secret** : Your_Gearment_Client_Secret"
### 
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi#section/Rate-Limiting)Rate Limiting
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
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi#section/Migration-Guide)Migration Guide
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
##  [](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook)List Webhook
Copy
  * Copy for LLM
Copy page as Markdown for LLMs
  * [ View as Markdown Open this page as Markdown ](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook.md)
  * [ Open in ChatGPT Get insights from ChatGPT ](https://chat.openai.com/?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.webhook.v1.vendorwebhookapi%2Fapi.webhook.v1.vendorwebhookapi.vendorlistwebhook.md+and+answer+questions+based+on+the+content.)
  * [ Open in Claude Get insights from Claude ](https://claude.ai/new?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.webhook.v1.vendorwebhookapi%2Fapi.webhook.v1.vendorwebhookapi.vendorlistwebhook.md+and+answer+questions+based+on+the+content.)


####  [](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook/request)Request
List all registered webhooks
GET /api/v3/webhooks
Returns:
  * All registered webhooks for your account
  * Webhook status (active/inactive)
  * Event topics subscribed
  * Delivery URLs


Use cases:
  * Audit webhook configurations
  * Verify webhook setup
  * List active event subscriptions


[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook/request/query)Query
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook/t=request&in=query&path=filter.statuses)filter.statuses _Array of strings or numbers_ _(statuses)_
Filter by webhook status (e.g., to see only active webhooks)
Items Enum"STATUS_ACTIVE"2"STATUS_INACTIVE"3
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook/t=request&in=query&path=filter.store_ids)filter.store_ids _Array of strings_ _(store_ids)_
Filter by store IDs
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook/t=request&in=query&path=filter.team_ids)filter.team_ids _Array of strings_ _(team_ids)_
Filter by team IDs (internal use)
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook/t=request&in=query&path=filter.topics)filter.topics _Array of strings or numbers_ _(topics)_
Filter by event topics
Items Enum"TOPIC_ORDER_COMPLETED"2"TOPIC_ORDER_CANCELLED"3"TOPIC_TRACKING_ORDER_UPDATED"4"TOPIC_ORDER_ON_HOLD"5"TOPIC_SHIPPING_ADDRESS_VERIFIED"6+4 more
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook/t=request&in=query&path=filter.versions)filter.versions _Array of strings or numbers_ _(versions)_
Filter by webhook version
Items Enum"VERSION_V1"2"VERSION_V3"3
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook/t=request&in=query&path=filter.webhook_ids)filter.webhook_ids _Array of strings_ _(webhook_ids)_
Filter by specific webhook IDs
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook/t=request&in=query&path=paging.limit)paging.limit _integer_ _(int32)__(limit)_
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook/t=request&in=query&path=paging.page)paging.page _integer_ _(int32)__(page)_
get
/api/v3/webhooks
  * Production Server
https://apiv2.gearment.com/integration-handler/api/v3/webhooks
  * Sandbox Server
https://api.gearmentinc.com/integration-handler/api/v3/webhooks


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
  'https://apiv2.gearment.com/integration-handler/api/v3/webhooks?filter.statuses=STATUS_ACTIVE&filter.store_ids=store_abc123&filter.team_ids=team_abc123&filter.topics=TOPIC_ORDER_COMPLETED&filter.versions=VERSION_V1&filter.webhook_ids=wh_abc123&paging.limit=0&paging.page=0'
```

Try it
####  [](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook/response&c=200)Responses
  1. 200
  2. 400
  3. 401
  4. 403
  5. 404
  6. 500

Expand all
Success
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook/response&c=200/body)Bodyapplication/json
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook/t=response&c=200&path=status)status _string_ _(status)_
Response status: "success" or "error"
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook/t=response&c=200&path=message)message _string_ _(message)_
Human-readable message
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook/t=response&c=200&path=paging)paging _object_ _(common.type.v1.PagingResponse)_
+Show 4 properties
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorlistwebhook/t=response&c=200&path=data)data _Array of objects_ _(data)_
List of registered webhooks Each webhook includes: ID, topic, delivery URL, status, created_at
+Show 9 array properties
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
##  [](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook)Create Webhook
Copy
  * Copy for LLM
Copy page as Markdown for LLMs
  * [ View as Markdown Open this page as Markdown ](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook.md)
  * [ Open in ChatGPT Get insights from ChatGPT ](https://chat.openai.com/?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.webhook.v1.vendorwebhookapi%2Fapi.webhook.v1.vendorwebhookapi.vendorcreatewebhook.md+and+answer+questions+based+on+the+content.)
  * [ Open in Claude Get insights from Claude ](https://claude.ai/new?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.webhook.v1.vendorwebhookapi%2Fapi.webhook.v1.vendorwebhookapi.vendorcreatewebhook.md+and+answer+questions+based+on+the+content.)


####  [](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook/request)Request
Register a new webhook for event notifications
POST /api/v3/webhooks Content-Type: application/json
Available topics:
  * VENDOR_WEBHOOK_TOPIC_ORDER_COMPLETED: Order fulfillment completed
  * VENDOR_WEBHOOK_TOPIC_ORDER_CANCELED: Order was cancelled
  * VENDOR_WEBHOOK_TOPIC_TRACKING_UPDATED: Shipping tracking updated
  * VENDOR_WEBHOOK_TOPIC_ADDRESS_UNVERIFIED: Shipping address validation failed


Security:
  * Webhooks are sent via HTTPS POST
  * Include signature header for verification
  * Must respond with 200 OK within 30 seconds


Use cases:
  * Automate order status updates
  * Sync tracking information
  * Alert customers of shipment


[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook/request/body)Bodyapplication/jsonrequired
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook/t=request&path=status)status _string or number_ _(api.webhook.v1.VendorWebhook.Status)_
Enum"STATUS_ACTIVE"2"STATUS_INACTIVE"3
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook/t=request&path=topic)topic _string or number_ _(api.webhook.v1.VendorWebhook.Topic)_
Enum"TOPIC_ORDER_COMPLETED"2"TOPIC_ORDER_CANCELLED"3"TOPIC_TRACKING_ORDER_UPDATED"4"TOPIC_ORDER_ON_HOLD"5"TOPIC_SHIPPING_ADDRESS_VERIFIED"6+4 more
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook/t=request&path=name)name _string_ _(name)__< = 255 characters_
Human-readable webhook name (optional, helps identify webhook purpose, max length: 255 characters)
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook/t=request&path=version)version _string or number_ _(api.webhook.v1.VendorWebhook.Version)_
Enum"VERSION_V1"2"VERSION_V3"3
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook/t=request&path=delivery_url)delivery_url _string_ _(uri)__(delivery_url)__[ 1 .. 2048 ] characters_
HTTPS URL to receive webhook POST requests (required, must be publicly accessible and respond within 30 seconds, must use HTTPS)
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook/t=request&path=store_id)store_id _string_ _(store_id)_
Optional store ID to filter events (if provided, only events for this store will trigger the webhook)
post
/api/v3/webhooks
  * Production Server
https://apiv2.gearment.com/integration-handler/api/v3/webhooks
  * Sandbox Server
https://api.gearmentinc.com/integration-handler/api/v3/webhooks


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
  https://apiv2.gearment.com/integration-handler/api/v3/webhooks \
  -H 'Content-Type: application/json' \
  -d '{
    "status": "STATUS_ACTIVE",
    "topic": "TOPIC_ORDER_COMPLETED",
    "name": "Production Order Completed Notifications",
    "version": "VERSION_V1",
    "delivery_url": "https://yourapp.com/webhooks/gearment/orders",
    "store_id": "store_abc123"
  }'
```

Try it
####  [](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook/response&c=200)Responses
  1. 200
  2. 400
  3. 401
  4. 403
  5. 404
  6. 500

Expand all
Success
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook/response&c=200/body)Bodyapplication/json
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook/t=response&c=200&path=status)status _string_ _(status)_
Response status: "success" or "error"
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook/t=response&c=200&path=message)message _string_ _(message)_
Human-readable message Success: "Webhook created successfully" Error: "Invalid delivery URL" or "Duplicate webhook"
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendorcreatewebhook/t=response&c=200&path=data)data _object_ _(api.webhook.v1.VendorWebhook)_
+Show 9 properties
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
    "webhook_id": "string",
    "topic": "TOPIC_ORDER_COMPLETED",
    "status": "STATUS_ACTIVE",
    "delivery_url": "http://example.com",
    "version": "VERSION_V1",
    "created_at": "2023-01-15T01:30:15.01Z",
    "updated_at": "2023-01-15T01:30:15.01Z",
    "team_id": "string",
    "store_id": "string"
  }
}

```

#### Feedback documents for customer support
##  [](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendordeletewebhook)Delete Webhook
Copy
  * Copy for LLM
Copy page as Markdown for LLMs
  * [ View as Markdown Open this page as Markdown ](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendordeletewebhook.md)
  * [ Open in ChatGPT Get insights from ChatGPT ](https://chat.openai.com/?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.webhook.v1.vendorwebhookapi%2Fapi.webhook.v1.vendorwebhookapi.vendordeletewebhook.md+and+answer+questions+based+on+the+content.)
  * [ Open in Claude Get insights from Claude ](https://claude.ai/new?q=Read+https%3A%2F%2Fdevelopers.gearment.com%2Fapi%2Fapi.webhook.v1.vendorwebhookapi%2Fapi.webhook.v1.vendorwebhookapi.vendordeletewebhook.md+and+answer+questions+based+on+the+content.)


####  [](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendordeletewebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendordeletewebhook/request)Request
Delete a webhook subscription
DELETE /api/v3/webhooks/{webhook_id}
Use cases:
  * Remove unused webhooks
  * Update webhook configuration (delete + recreate)


delete
/api/v3/webhooks/{webhook_id}
  * Production Server
https://apiv2.gearment.com/integration-handler/api/v3/webhooks/{webhook_id}
  * Sandbox Server
https://api.gearmentinc.com/integration-handler/api/v3/webhooks/{webhook_id}


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
curl -i -X DELETE \
  'https://apiv2.gearment.com/integration-handler/api/v3/webhooks/{webhook_id}'
```

Try it
####  [](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendordeletewebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendordeletewebhook/response&c=200)Responses
  1. 200
  2. 400
  3. 401
  4. 403
  5. 404
  6. 500

Expand all
Success
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendordeletewebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendordeletewebhook/response&c=200/body)Bodyapplication/json
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendordeletewebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendordeletewebhook/t=response&c=200&path=status)status _string_ _(status)_
Response status: "success" or "error"
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendordeletewebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendordeletewebhook/t=response&c=200&path=message)message _string_ _(message)_
Human-readable message Success: "Webhook deleted successfully" Error: "Webhook not found"
[](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendordeletewebhook#api.webhook.v1.vendorwebhookapi/api.webhook.v1.vendorwebhookapi.vendordeletewebhook/t=response&c=200&path=data)data _object_ _(api.webhook.v1.VendorWebhook)_
+Show 9 properties
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
    "webhook_id": "string",
    "topic": "TOPIC_ORDER_COMPLETED",
    "status": "STATUS_ACTIVE",
    "delivery_url": "http://example.com",
    "version": "VERSION_V1",
    "created_at": "2023-01-15T01:30:15.01Z",
    "updated_at": "2023-01-15T01:30:15.01Z",
    "team_id": "string",
    "store_id": "string"
  }
}

```

#### Feedback documents for customer support
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
