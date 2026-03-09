# Dashboard Setup Guide

This guide takes ~20 minutes. Follow each step in order.

---

## Step 1 — Create the GitHub Repo

1. Go to https://github.com/new
2. Name it: `dashboard`
3. Set visibility to **Public** (GitHub Pages is free on public repos)
4. Leave all other defaults — click **Create repository**
5. Push the files from this folder:
   ```bash
   cd /path/to/this/folder
   git init
   git add .
   git commit -m "Initial dashboard"
   git branch -M main
   git remote add origin https://github.com/axhasan/dashboard.git
   git push -u origin main
   ```

---

## Step 2 — Enable GitHub Pages

1. Go to https://github.com/axhasan/dashboard/settings/pages
2. Under **Source**, choose **Deploy from a branch**
3. Set Branch to `main`, folder to `/ (root)` — click **Save**
4. In ~2 minutes your dashboard will be live at: `https://axhasan.github.io/dashboard`

> **Your existing site** at `axhasan.github.io` lives in a different repo and is completely unaffected.

---

## Step 3 — Google Cloud Setup (Gmail + Calendar + OAuth)

This enables Gmail, Calendar, and the Google Sign-In button.

1. Go to https://console.cloud.google.com
2. Click **Select a project → New Project**. Name it `Dashboard`.
3. In the left menu → **APIs & Services → Library**
   - Search and enable **Gmail API**
   - Search and enable **Google Calendar API**
4. Go to **APIs & Services → OAuth consent screen**
   - Choose **External** → click Create
   - App name: `My Dashboard`
   - User support email: `ahasan@gmail.com`
   - Developer contact email: `ahasan@gmail.com`
   - Click **Save and Continue** through all steps
   - On the **Test users** page, add `ahasan@gmail.com`
5. Go to **APIs & Services → Credentials → + Create Credentials → OAuth 2.0 Client ID**
   - Application type: **Web application**
   - Name: `Dashboard Web`
   - Authorized JavaScript origins — add both:
     - `https://axhasan.github.io`
     - `http://localhost` (for local testing)
   - Authorized redirect URIs — add:
     - `https://axhasan.github.io/dashboard`
   - Click **Create**
   - **Copy the Client ID** (looks like `123456789-abc.apps.googleusercontent.com`)

---

## Step 4 — Get a Claude API Key

1. Go to https://console.anthropic.com
2. Click **API Keys → + Create Key**
3. Name it `Dashboard` — copy the key (starts with `sk-ant-`)

---

## Step 5 — Get an Alpha Vantage Key (Stocks)

1. Go to https://www.alphavantage.co/support/#api-key
2. Fill in the free registration form
3. Your API key will be shown on the page — copy it

---

## Step 6 — Get an OpenWeatherMap Key (Weather)

1. Go to https://home.openweathermap.org/users/sign_up
2. Create a free account
3. Go to **API Keys** tab — copy the default key
4. Note: The key activates within ~10 minutes of creation

---

## Step 7 — Create a GitHub Personal Access Token (PAT)

This allows the dashboard to read and write your tracker data files.

1. Go to https://github.com/settings/tokens/new
2. Note: `Dashboard data access`
3. Expiration: choose 1 year (or no expiration)
4. Scopes: check **repo** (includes contents read/write)
5. Click **Generate token** — copy it (starts with `ghp_`)
6. ⚠️ You only see it once — save it somewhere safe

---

## Step 8 — Configure the Dashboard

1. Go to https://axhasan.github.io/dashboard
2. Click **⚙ Configure API Keys** (small link below the sign-in button)
3. Paste in all 5 values:
   - Google OAuth Client ID
   - Claude API Key
   - Alpha Vantage Key
   - OpenWeather API Key
   - GitHub PAT
4. Click **Save & Continue**
5. Click **Sign in with Google** and authorize with `ahasan@gmail.com`

---

## Step 9 — Set Up the LinkedIn 6am Scanner

This requires generating a Gmail OAuth refresh token once.

### 9a. Install Python dependencies locally

```bash
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### 9b. Run this script once to generate your refresh token

Create a file called `get_token.py` and run it:

```python
from google_auth_oauthlib.flow import InstalledAppFlow
import json

# Replace these with your Google Cloud credentials
CLIENT_ID = "YOUR_GOOGLE_CLIENT_ID"
CLIENT_SECRET = "YOUR_GOOGLE_CLIENT_SECRET"  # from Google Cloud Console

flow = InstalledAppFlow.from_client_config(
    {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    },
    scopes=["https://www.googleapis.com/auth/gmail.readonly"],
)

# Opens your browser to authorize
creds = flow.run_local_server(port=0)
print("\n\nYour refresh token (copy this):")
print(creds.refresh_token)
print("\nYour client secret (if you need it):")
print(CLIENT_SECRET)
```

Run it: `python get_token.py` — authorize in the browser, copy the printed refresh token.

> To get your `CLIENT_SECRET`: In Google Cloud Console → Credentials → click your OAuth Client → copy the Client Secret.

### 9c. Add GitHub Actions Secrets

1. Go to https://github.com/axhasan/dashboard/settings/secrets/actions
2. Add these 3 secrets (click **New repository secret** for each):

| Secret Name | Value |
|---|---|
| `GMAIL_REFRESH_TOKEN` | The refresh token from step 9b |
| `GMAIL_CLIENT_ID` | Your Google OAuth Client ID |
| `GMAIL_CLIENT_SECRET` | Your Google OAuth Client Secret |

### 9d. Test the scanner manually

1. Go to https://github.com/axhasan/dashboard/actions
2. Click **LinkedIn Opportunity Scanner**
3. Click **Run workflow → Run workflow**
4. Check the run logs — if successful, check your dashboard's Opportunities tab

The scanner will now run automatically at **6am Pacific Time every day**.

---

## No Overlap with Existing Site

Your existing site lives at `axhasan.github.io` (in a repo named `axhasan.github.io`).
This dashboard lives at `axhasan.github.io/dashboard` (in the separate `dashboard` repo).

They are completely independent — different repos, different deployments, no shared files.

---

## Privacy & Access Control

- The dashboard uses **Google OAuth** locked to `ahasan@gmail.com`
- Even though the repo is public, the app blocks anyone who signs in with a different Google account
- API keys are stored in your browser's localStorage — never in the repo
- The only data in the repo is your `trackers.json` and `opportunities.json` — which are just JSON files without credentials

---

## Troubleshooting

**"Error 400: redirect_uri_mismatch"** — Go back to Google Cloud Console → Credentials → your OAuth client → add `https://axhasan.github.io/dashboard` to Authorized redirect URIs.

**Stocks show "—"** — Alpha Vantage free tier allows 25 calls/day. If you've exceeded that, try again tomorrow. Consider upgrading or caching.

**Weather not loading** — New OpenWeatherMap keys take up to 10 minutes to activate.

**LinkedIn scanner not finding emails** — Check that your Gmail account actually receives LinkedIn job emails. You can test by going to Actions → manually running the workflow and reading the logs.

**GitHub save fails** — Make sure your PAT has `repo` scope and hasn't expired.
