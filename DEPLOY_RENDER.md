# Deploy HireX Backend to Render (Free)

This guide deploys your FastAPI backend to Render's free tier so your Flutter app works from any network.

## Prerequisites

1. GitHub account
2. Render account (sign up at https://render.com — free)
3. Your backend code pushed to GitHub

## Step 1: Prepare Firebase Credentials

Render doesn't support uploading files, so we'll pass the Firebase credentials as an environment variable.

**In your terminal (inside `hirex_backend` folder):**

```bash
python -c "import json; f=open('firebase-credentials.json'); print(json.dumps(json.load(f)))"
```

Copy the entire output (it's a single-line JSON string). You'll paste this in Render as `FIREBASE_CREDENTIALS_JSON`.

## Step 2: Push to GitHub

Make sure your `hirex_backend` folder is in a GitHub repository. If not:

```bash
cd hirex_backend
git init
git add .
git commit -m "Initial backend commit"
git remote add origin https://github.com/YOUR_USERNAME/hirex-backend.git
git push -u origin main
```

## Step 3: Deploy on Render

1. Go to https://dashboard.render.com
2. Click **New +** → **Web Service**
3. Connect your GitHub repo
4. Render will auto-detect the `render.yaml` and show the service config
5. Click **Create Web Service**

## Step 4: Add Environment Variables

In the Render dashboard, go to your service → **Environment** tab and add:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | Your Neon PostgreSQL connection string |
| `FIREBASE_CREDENTIALS_JSON` | Paste the JSON string from Step 1 |
| `SECRET_KEY` | Generate a strong random key |
| `ALLOWED_ORIGINS` | `*` (or your Flutter app domain) |
| `AWS_ACCESS_KEY_ID` | Your AWS access key |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key |
| `AWS_S3_BUCKET` | Your S3 bucket name |
| `AWS_CLOUDFRONT_URL` | Your CloudFront URL |
| `RAZORPAY_KEY_ID` | Your Razorpay test key |
| `RAZORPAY_KEY_SECRET` | Your Razorpay secret |

Click **Save Changes**. Render will redeploy automatically.

## Step 5: Get Your Backend URL

Once deployed, Render gives you a URL like:
```
https://hirex-backend-xyz123.onrender.com
```

Copy this URL.

## Step 6: Update Flutter App

In `hirex_app/.env`, update:

```env
API_BASE_URL=https://hirex-backend-xyz123.onrender.com
```

Replace with your actual Render URL.

## Step 7: Test

Hot restart your Flutter app. Google Sign-In and all API calls will now work from any network!

---

## Free Tier Limitations

- Render free tier spins down after 15 minutes of inactivity
- First request after spin-down takes ~30 seconds (cold start)
- For production, upgrade to paid tier ($7/month) for always-on service

## Alternative: Railway

If Render doesn't work, try Railway (also free):

1. Go to https://railway.app
2. Click **New Project** → **Deploy from GitHub**
3. Select your repo
4. Add the same environment variables
5. Railway auto-detects the Dockerfile and deploys

Railway URL format: `https://hirex-backend-production.up.railway.app`

---

## Troubleshooting

**"Service Unavailable" on first request:**
- Free tier cold start — wait 30 seconds and retry

**"Invalid Firebase credentials":**
- Check `FIREBASE_CREDENTIALS_JSON` is a valid single-line JSON string
- No extra quotes or escaping

**CORS errors:**
- Set `ALLOWED_ORIGINS=*` in Render env vars
- Or add your specific domain: `https://yourapp.com`

**Database connection errors:**
- Verify `DATABASE_URL` is correct
- Neon free tier has connection limits — check your Neon dashboard
