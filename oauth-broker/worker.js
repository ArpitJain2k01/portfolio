/**
 * Decap CMS GitHub OAuth broker — Cloudflare Worker.
 *
 * Why this exists: Decap CMS runs in the browser on a static site and cannot
 * safely hold a GitHub OAuth *client secret*. GitHub's OAuth flow requires
 * exchanging a temporary code for a token using that secret server-side. This
 * tiny worker is that server-side piece: it starts the GitHub login and
 * completes the code→token exchange, then hands the token back to the CMS.
 *
 * It stores NO data and runs only during login. Two routes:
 *   GET /auth      → redirect the user to GitHub's consent screen
 *   GET /callback  → exchange ?code for a token, post it back to the CMS window
 *
 * Required secrets (set with: wrangler secret put <NAME>):
 *   GITHUB_CLIENT_ID
 *   GITHUB_CLIENT_SECRET
 */

const GITHUB_AUTHORIZE = "https://github.com/login/oauth/authorize";
const GITHUB_TOKEN = "https://github.com/login/oauth/access_token";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/auth") {
      const redirectUri = `${url.origin}/callback`;
      const authUrl = new URL(GITHUB_AUTHORIZE);
      authUrl.searchParams.set("client_id", env.GITHUB_CLIENT_ID);
      authUrl.searchParams.set("redirect_uri", redirectUri);
      authUrl.searchParams.set("scope", "repo");
      authUrl.searchParams.set("state", crypto.randomUUID());
      return Response.redirect(authUrl.toString(), 302);
    }

    if (url.pathname === "/callback") {
      const code = url.searchParams.get("code");
      if (!code) return new Response("Missing code", { status: 400 });

      const tokenRes = await fetch(GITHUB_TOKEN, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          client_id: env.GITHUB_CLIENT_ID,
          client_secret: env.GITHUB_CLIENT_SECRET,
          code,
        }),
      });
      const data = await tokenRes.json();

      // Decap listens for a postMessage of the form:
      //   authorization:github:success:{"token":"...","provider":"github"}
      const status = data.access_token ? "success" : "error";
      const payload = data.access_token
        ? JSON.stringify({ token: data.access_token, provider: "github" })
        : JSON.stringify({ error: data.error || "no token" });

      const message = `authorization:github:${status}:${payload}`;
      const html = `<!doctype html><html><head><meta charset="utf-8"></head><body><script>
        (function () {
          var message = ${JSON.stringify(message)};
          function receive(e) {
            if (!window.opener) return;
            window.opener.postMessage(message, e.origin || "*");
          }
          window.addEventListener("message", receive, false);
          // Kick off the handshake: Decap replies to "authorizing:github",
          // then we send the result above.
          if (window.opener) {
            window.opener.postMessage("authorizing:github", "*");
          } else {
            document.body.innerHTML =
              "Login complete. You can close this window and return to the CMS.";
          }
        })();
      </script>Logging you in...</body></html>`;

      return new Response(html, {
        headers: { "Content-Type": "text/html; charset=utf-8" },
      });
    }

    return new Response("Decap OAuth broker. Use /auth to start.", {
      headers: { "Content-Type": "text/plain" },
    });
  },
};
