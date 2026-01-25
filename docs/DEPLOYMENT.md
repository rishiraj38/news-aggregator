# 🚀 Deployment Guide: Helix SaaS

Follow these exact steps to launch your application.

## 📋 Prerequisites Check

Ensure you have these credentials saved in a text file for easy copying:

1.  **Neon DB URL**: `postgres://...` (From Neon Dashboard)
2.  **Clerk Public Key**: `pk_test_...` (From Clerk Dashboard)
3.  **Clerk Secret Key**: `sk_test_...` (From Clerk Dashboard)
4.  **Google App Password**: (For email sending)
5.  **Groq API Key**: `gsk_...`

---

## Part 1: Prepare the Code

1.  **Open your terminal** in VS Code.
2.  **Run these commands** to sync the latest deployment files:
    ```bash
    git add .
    git commit -m "Ready for deployment: Added requirements.txt and workflows"
    git push origin main
    ```
3.  Wait for the command to finish.

---

## Part 2: Deploy Frontend (Vercel)

1.  **Go to Vercel**: [https://vercel.com/new](https://vercel.com/new)
2.  **Select Repository**: Click **Import** next to `news-aggregator`.
3.  **Configure Project**:
    - **Framework Preset**: Leave as `Next.js`.
    - **Root Directory**: Click `Edit` -> Select `web` folder -> Click `Continue`. **(Critical Step!)**
4.  **Environment Variables**:
    - Expand the **Environment Variables** section.
    - Add the following keys (Copy values from your local `.env`):
      - `DATABASE_URL`
      - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
      - `CLERK_SECRET_KEY`
      - `NEXT_PUBLIC_CLERK_SIGN_IN_URL` = `/sign-in`
      - `NEXT_PUBLIC_CLERK_SIGN_UP_URL` = `/sign-up`
5.  **Deploy**: Click **Deploy**.
6.  **Success**: Wait ~1 minute. You will see a confetti screen. Click the preview image to visit your live site!

---

## Part 3: Automate Backend (GitHub Actions)

Your backend runs on GitHub's free servers once a day.

1.  **Go to GitHub**: Open your repository page.
2.  **Navigate**: Click **Settings** (top tab) -> **Secrets and variables** (left sidebar) -> **Actions**.
3.  **Add Secrets**: Click **New repository secret** (green button) for each of these:
    - `DATABASE_URL`: (Paste your Neon URL)
    - `GROQ_API_KEY`: (Paste your Groq Key)
    - `MY_EMAIL`: (Paste your Gmail address)
    - `APP_PASSWORD`: (Paste your Google App Password)
    - `WEBSHARE_USERNAME`: (Optional, if using proxies)
    - `WEBSHARE_PASSWORD`: (Optional, if using proxies)

---

## Part 4: Verify It Works

1.  **Trigger Backend**:
    - Go to **Actions** tab in GitHub.
    - Click **Daily AI Digest** on the left.
    - Click **Run workflow** (button on right) -> **Run workflow**.
    - Watch it turn 🟡 (Running) then 🟢 (Success).
2.  **Check Email**: You should receive a digest email within 2-3 minutes.
3.  **Visit Site**: Login to your Vercel URL. Your dashboard should load!

🎉 **Congratulations! Your SaaS is live.**
