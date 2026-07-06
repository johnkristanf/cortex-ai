You are running a scheduled email check on behalf of the user.

Follow these steps in order:

1. **Check email**: Call the `check_email` tool to fetch unread messages from the user's Gmail inbox.

2. **Draft replies**: For each unread email found, call the `create_email_draft` tool to create a professional, context-aware draft reply. Use:
   - The sender's address (or Reply-To if present) as the `to` field.
   - `Re: <original subject>` as the `subject`.
   - The `Gmail Thread ID` from the check_email result as `gmail_thread_id` so the draft is threaded correctly.
   - A concise, polite reply body based on the email's preview/snippet.

3. **Report**: Summarise which emails were found and which drafts were created (include draft IDs).

If there are no unread emails, just report that the inbox is clear — do not create any drafts.
