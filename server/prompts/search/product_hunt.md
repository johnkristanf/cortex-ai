Use the `product_hunt_search` tool to scrape the Product Hunt homepage and get the latest trending products.

From the scraped content, extract and present the top 3 products for each of these time periods:
- **Today** (Top Products Launching Today)
- **Yesterday** (Yesterday's Top Products)
- **Last Week** (Last Week's Top Products)
- **Last Month** (Last Month's Top Products)

For each product include:
- Product name and tagline
- A brief description of what it does
- Number of upvotes — **important**: in the scraped content each product often shows two numbers in sequence (e.g. `85` then `378`). The **first** number is the **comment count**; the **second, larger** number is the **upvote count**. If only one number appears, that is the upvote count. Never report the comment count as upvotes.
- Direct link to the Product Hunt page

Organise the response cleanly using Markdown with separate sections per time period (e.g., ## 🔥 Today, ## 📅 Yesterday, ## 📆 Last Week, ## 🗓️ Last Month).
