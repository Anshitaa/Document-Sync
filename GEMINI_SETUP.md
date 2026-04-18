# 🔑 Google Gemini API Setup Guide

## Step 1: Get Your Free API Key

1. **Go to Google AI Studio**
   - Visit: https://makersuite.google.com/app/apikey
   - Sign in with your Google account

2. **Create API Key**
   - Click "Create API Key"
   - Select "Create API key in new project" (or use existing)
   - Copy your API key (starts with `AIza...`)

## Step 2: Add to Your Project

1. **Open your `.env` file:**
   ```bash
   cd path/to/docu-sync/services/api
   nano .env
   ```

2. **Update the Gemini API key:**
   ```bash
   # Google Gemini Configuration
   GEMINI_API_KEY=AIza...your_actual_key_here
   
   # GitHub Configuration (keep your existing values)
   GITHUB_TOKEN=ghp_...
   GITHUB_REPO=Anshitaa/DocumentSync
   GITHUB_REPO_OWNER=Anshitaa
   GITHUB_REPO_NAME=DocumentSync
   ```

3. **Save and exit** (Ctrl+O, Enter, Ctrl+X)

## Step 3: Install Dependencies

```bash
cd path/to/docu-sync/services/api
pip install -r requirements.txt
```

## Step 4: Restart Your App

```bash
# Stop the current app (Ctrl+C in the terminal where it's running)
# Then restart:
python app.py
```

## Step 5: Test It!

Go to http://localhost:8080 and try the "Documentation Writer" feature!

---

## 📊 Free Tier Limits

- **15 requests per minute**
- **1,500 requests per day**
- **1 million tokens per month**

**This is more than enough for your portfolio project!** 🎉

---

## 🔗 Useful Links

- **API Key Dashboard**: https://makersuite.google.com/app/apikey
- **Gemini Documentation**: https://ai.google.dev/docs
- **Pricing**: https://ai.google.dev/pricing (free tier is generous!)
