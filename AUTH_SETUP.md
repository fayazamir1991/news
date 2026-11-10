# Google accounts and private bookmarks

Supabase Auth uses Google OAuth with PKCE and identity scopes only (`openid email profile`). Gmail messages are never accessed. `auth-public.json` contains only a publishable key. Never put a service-role key or Google client secret in this repository, build variables, or frontend.

## Backend

Project: `dideban-news`, ref `arkukeyeoobhbsqgiapv`.
The `bookmarks` migration has already been applied to the hosted project. `supabase/migrations/001_bookmarks.sql` documents the schema. RLS limits every read, insertion and deletion to `auth.uid() = user_id`. Anonymous access and updates are denied. Only item IDs and save timestamps are stored alongside the Supabase Auth account.

## Activate Google login

1. Create a Web application OAuth client in [Google Cloud Console](https://console.cloud.google.com/apis/credentials). Configure the consent screen and intended audience. Testing mode permits registered test users only; publish the consent app when ready for public access.
2. Register this exact authorized redirect URI in Google:
   `https://arkukeyeoobhbsqgiapv.supabase.co/auth/v1/callback`
3. In [Supabase provider settings](https://supabase.com/dashboard/project/arkukeyeoobhbsqgiapv/auth/providers), enable Google and enter the Google Client ID and Client Secret there. Keep the secret out of chat and GitHub.
4. In Supabase Authentication → URL Configuration, set Site URL to `https://visionwatcher.vercel.app`. Add the exact application callback `https://visionwatcher.vercel.app/auth/callback/` to the redirect allow list. Avoid broad preview-domain wildcards for production.
5. Open the site → حساب → ورود با Google. Verify the full consent/return flow, save an item and open ذخیره‌شده‌ها on another device using the same Google account. A second account must have its own independent list.

Creating the database does not enable Google OAuth. Until enabled, the site explains that Google setup is incomplete. OAuth callback pages and query parameters never enter the service-worker cache. Private cross-origin Supabase requests are not cached by the worker. Logout clears private UI. Saved item IDs remain in the database when reports change; deleted reports appear as unavailable entries that the user can remove.

## Builds

`auth-public.json` supplies the public project URL/key for Vercel and Docker. Optional `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` environment variables override defaults. Docker accepts the same build arguments. Builds reject non-publishable keys. Google secrets belong only in Supabase provider settings.

## Verification

`python3 -m unittest discover -s tests` validates stable IDs and generated pages. `node tests/bookmarks-browser.cjs` checks the account UI using an SDK mock, not real Google consent. `supabase/tests/bookmarks_rls.sql` checks real database isolation in a rolled-back transaction. After provider setup, a live end-to-end Google and two-device test remains required.

Sources: [Google provider](https://supabase.com/docs/guides/auth/social-login/auth-google), [PKCE](https://supabase.com/docs/guides/auth/sessions/pkce-flow), [RLS](https://supabase.com/docs/guides/database/postgres/row-level-security).

## Google Branding URLs

- Application home page: `https://visionwatcher.vercel.app/`
- Privacy policy: `https://visionwatcher.vercel.app/privacy/`
- Terms of service: `https://visionwatcher.vercel.app/terms/`

The Google authorized redirect URI remains the Supabase callback above; it is different from the application's callback allowlisted in Supabase.

Account controls and PWA installation live at `/account/`. Bookmarks remain at `/bookmarks/`; daily survey cards and their dedicated pages share the original item ID. Navigation rearrangement does not change OAuth callbacks, scopes, session storage, RLS or provider configuration.
