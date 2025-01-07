export const getOAuth2Template = (oauth1Url: string) => `
<!DOCTYPE html>
<html>
  <head>
    <title>Twitter OAuth</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
      body { margin: 0; padding: 20px; font-family: system-ui, -apple-system, sans-serif; }
      .container { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; }
      .title { margin-bottom: 20px; }
      .description { margin-bottom: 20px; }
      .button { background-color: #1da1f2; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 500; }
    </style>
  </head>
  <body>
    <div class="container">
      <h2 class="title">OAuth 2.0 Authorization Complete</h2>
      <p class="description">Please click the button below to complete Twitter OAuth 1.0a authorization.</p>
      <a href="${oauth1Url}" class="button">Continue with Twitter OAuth 1.0a</a>
    </div>
  </body>
</html>
`;

export const getSuccessTemplate = () => `
<!DOCTYPE html>
<html>
  <head>
    <title>Twitter OAuth Success</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
      body { margin: 0; padding: 20px; font-family: system-ui, -apple-system, sans-serif; }
      .container { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; }
      .title { margin-bottom: 20px; color: #10b981; }
      .description { margin-bottom: 20px; }
      .button { background-color: #6b7280; color: white; padding: 12px 24px; border-radius: 6px; border: none; cursor: pointer; font-weight: 500; }
    </style>
  </head>
  <body>
    <div class="container">
      <h2 class="title">✓ Twitter Connected Successfully</h2>
      <p class="description">You can now close this window.</p>
      <button onclick="window.close()" class="button">Close Window</button>
    </div>
  </body>
</html>
`;