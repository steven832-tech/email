# 📁 Exact File Structure for Your GitHub Repo

Paste these files in EXACTLY this folder structure:

```
your-repo/
├── .github/
│   └── workflows/
│       └── smtp-verify.yml       ← GitHub Actions workflow
└── api/
    └── verify.py                 ← Python SMTP script
```

---

## Step 1 — Create the folders & files on GitHub

1. Go to your GitHub repo
2. Click **Add file → Create new file**
3. In the filename box type:
   `.github/workflows/smtp-verify.yml`
   (GitHub will auto-create the folders)
4. Paste the contents of `smtp-verify.yml`
5. Click **Commit changes**

6. Click **Add file → Create new file** again
7. Type filename: `api/verify.py`
8. Paste the contents of `verify.py`
9. Click **Commit changes**

---

## Step 2 — Create a GitHub Personal Access Token

1. Go to: https://github.com/settings/tokens/new
2. Note: `SMTP Verifier Token`
3. Expiration: 90 days (or No expiration)
4. Scopes — tick these:
   - ✅ `repo` (full repo access)
   - ✅ `workflow` (trigger workflows)
5. Click **Generate token**
6. **Copy the token immediately** — you won't see it again

---

## Step 3 — Add token to your email finder tool

In the tool widget, paste:
- Your GitHub username  (e.g. `johnsmith`)
- Your repo name        (e.g. `email-finder`)
- Your token            (e.g. `ghp_xxxxxxxxxxxx`)

The tool will:
1. Call GitHub API to trigger `smtp-verify.yml`
2. Poll every 4 seconds until the job finishes
3. Download the result JSON
4. Show ✅ Delivered / ❌ Invalid / ❓ Uncertain per email

---

## How the SMTP check works (no email is sent)

```
Tool  →  GitHub API (trigger workflow)
            ↓
       Ubuntu runner starts
            ↓
       Python looks up MX records for domain
            ↓
       Connects to mail server on port 25
            ↓
       Sends: HELO / MAIL FROM / RCPT TO <email>
            ↓
       250 = ✅ mailbox exists
       550 = ❌ mailbox does not exist
       4xx = ❓ greylisted / uncertain
            ↓
       RSET + QUIT  (no email sent)
            ↓
       Result saved as artifact JSON
            ↓
Tool  ←  Downloads artifact, shows result
```

---

## SMTP Response Codes

| Code | Meaning | Result |
|------|---------|--------|
| 250  | Mailbox OK | ✅ Delivered |
| 251  | Will forward | ✅ Delivered |
| 550  | No such mailbox | ❌ Invalid |
| 551-554 | Rejected | ❌ Invalid |
| 421  | Server unavailable | ❓ Uncertain |
| 450-452 | Greylisted / temp fail | ❓ Uncertain |
| -4   | Port 25 blocked | ❓ Try again |
