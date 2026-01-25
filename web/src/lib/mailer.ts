import nodemailer from "nodemailer";

export async function sendWelcomeEmail(toEmail: string, userName: string) {
  const transporter = nodemailer.createTransport({
    service: "gmail",
    auth: {
      user: process.env.MY_EMAIL,
      pass: process.env.APP_PASSWORD,
    },
  });

  const htmlContent = `
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <style>
        body { font-family: 'Helvetica Neue', Arial, sans-serif; background-color: #000; color: #fff; margin: 0; padding: 0; }
        .container { max-width: 600px; margin: 0 auto; background-color: #111; border: 1px solid #333; border-radius: 8px; overflow: hidden; }
        .header { background: linear-gradient(90deg, #6b21a8, #a855f7); padding: 30px; text-align: center; }
        .logo { font-size: 28px; font-weight: bold; color: #fff; text-transform: uppercase; letter-spacing: 2px; }
        .content { padding: 40px 30px; line-height: 1.6; color: #cccccc; }
        .h1 { color: #fff; font-size: 24px; margin-bottom: 20px; }
        .btn { display: inline-block; padding: 12px 24px; background-color: #a855f7; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 20px; }
        .footer { background-color: #0a0a0a; padding: 20px; text-align: center; font-size: 12px; color: #666; border-top: 1px solid #222; }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <div class="logo">Helix</div>
        </div>
        <div class="content">
          <h1 class="h1">Welcome to the Future, ${userName}.</h1>
          <p>Thank you for choosing Helix as your personal knowledge agent. We are thrilled to have you on board.</p>
          <p>Your agent is currently analyzing thousands of data points to curate a personalized intelligence feed just for you. Specifically tailored to your interests in <strong>AI and Technology</strong>.</p>
          <p>Our autonomous pipeline runs every 24 hours. Expect your first bespoke digest shortly.</p>
          
          <center>
            <a href="http://localhost:3000/dashboard" class="btn">Go to Dashboard</a>
          </center>
        </div>
        <div class="footer">
          &copy; 2026 Helix Intelligence. All rights reserved.<br>
          Automated by Autonomous Agents.
        </div>
      </div>
    </body>
    </html>
  `;

  try {
    const info = await transporter.sendMail({
      from: `"Helix Intelligence" <${process.env.MY_EMAIL}>`,
      to: toEmail,
      subject: "Welcome to your Personal Intelligence Feed",
      html: htmlContent,
    });
    console.log("Welcome email sent:", info.messageId);
    return true;
  } catch (error) {
    console.error("Error sending welcome email:", error);
    return false;
  }
}
