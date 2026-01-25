import nodemailer from "nodemailer";

interface Digest {
  id: string;
  title: string;
  summary: string;
  url: string;
  source: string;
  created_at: Date;
}

interface User {
  email: string;
  name: string;
}

const transporter = nodemailer.createTransporter({
  host: process.env.SMTP_HOST,
  port: parseInt(process.env.SMTP_PORT || "587"),
  secure: false,
  auth: {
    user: process.env.MY_EMAIL,
    pass: process.env.APP_PASSWORD,
  },
});

export async function sendWelcomeEmail(user: User, digests: Digest[]) {
  const articleCards = digests
    .slice(0, 10)
    .map(
      (digest, index) => `
    <div style="background: #f8f9fa; border-left: 4px solid #4f46e5; padding: 16px; margin: 16px 0; border-radius: 8px;">
      <h3 style="margin: 0 0 8px 0; color: #1f2937; font-size: 18px;">${index + 1}. ${digest.title}</h3>
      <p style="margin: 0 0 12px 0; color: #4b5563; line-height: 1.6;">${digest.summary}</p>
      <div style="display: flex; justify-content: space-between; align-items: center; font-size: 14px;">
        <span style="color: #6b7280;">📰 ${digest.source}</span>
        <a href="${digest.url}" style="background: #4f46e5; color: white; padding: 8px 16px; text-decoration: none; border-radius: 6px; font-weight: 500;">Read Article →</a>
      </div>
    </div>
  `,
    )
    .join("");

  const htmlContent = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f3f4f6;">
  <div style="max-width: 600px; margin: 0 auto; background: white;">
    <!-- Header -->
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; text-align: center;">
      <h1 style="color: white; margin: 0; font-size: 32px; font-weight: 700;">Welcome to Helix! 🎉</h1>
      <p style="color: #e0e7ff; margin: 12px 0 0 0; font-size: 18px;">Your AI News Digest Has Arrived</p>
    </div>

    <!-- Trial Notification -->
    <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 20px; margin: 20px;">
      <div style="display: flex; align-items: center; gap: 12px;">
        <span style="font-size: 24px;">⏰</span>
        <div>
          <h3 style="margin: 0 0 4px 0; color: #92400e; font-size: 16px; font-weight: 600;">Your 30-Day Trial Has Started!</h3>
          <p style="margin: 0; color: #78350f; font-size: 14px;">You have <strong>30 days</strong> remaining to explore all features.</p>
        </div>
      </div>
    </div>

    <!-- Content -->
    <div style="padding: 20px;">
      <p style="color: #374151; font-size: 16px; line-height: 1.6;">Hi ${user.name || "there"},</p>
      
      <p style="color: #374151; font-size: 16px; line-height: 1.6;">
        Welcome to <strong>Helix</strong>! We're excited to have you on board. Your personalized AI news digest is ready. Every day, we'll curate the latest and most relevant AI news just for you.
      </p>

      <h2 style="color: #1f2937; font-size: 24px; margin: 32px 0 16px 0; padding-bottom: 12px; border-bottom: 2px solid #e5e7eb;">
        📰 Today's Top AI News
      </h2>

      ${articleCards}

      <!-- CTA Button -->
      <div style="text-align: center; margin: 40px 0;">
        <a href="${process.env.NEXT_PUBLIC_APP_URL || "https://helix.vercel.app"}/dashboard" 
           style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 16px 40px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
          Visit Your Dashboard →
        </a>
      </div>

      <div style="background: #f3f4f6; border-radius: 8px; padding: 20px; margin: 32px 0;">
        <h3 style="margin: 0 0 12px 0; color: #1f2937; font-size: 18px;">💡 What's Next?</h3>
        <ul style="color: #4b5563; line-height: 1.8; padding-left: 20px; margin: 0;">
          <li>Check your dashboard daily for personalized AI news</li>
          <li>Customize your interests to get more relevant content</li>
          <li>Enjoy your 30-day free trial with full access</li>
        </ul>
      </div>

      <p style="color: #6b7280; font-size: 14px; line-height: 1.6; margin-top: 32px;">
        Questions or feedback? Just reply to this email - we'd love to hear from you!
      </p>

      <p style="color: #374151; font-size: 16px; margin-top: 24px;">
        Happy reading! 🚀<br>
        <strong>The Helix Team</strong>
      </p>
    </div>

    <!-- Footer -->
    <div style="background: #f9fafb; padding: 24px; text-align: center; border-top: 1px solid #e5e7eb;">
      <p style="color: #9ca3af; font-size: 12px; margin: 0;">
        You're receiving this because you signed up for Helix.<br>
        © ${new Date().getFullYear()} Helix. All rights reserved.
      </p>
    </div>
  </div>
</body>
</html>
  `;

  await transporter.sendMail({
    from: `"Helix - AI News Digest" <${process.env.MY_EMAIL}>`,
    to: user.email,
    subject: "Welcome to Helix - Your AI Digest Awaits! 🚀",
    html: htmlContent,
  });
}
