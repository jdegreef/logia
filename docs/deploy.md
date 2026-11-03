# Deploying logia.faith

The site is static: Render runs `python3 scripts/build_site.py` and serves
`site/`. `render.yaml` holds the settings. DNS is on Cloudflare.

## 1. Create the site on Render

1. Render Dashboard > **New** > **Blueprint**, pick `jdegreef/logia`, branch
   `main`, and apply. This creates the static site `logia`.
2. Wait for the first deploy, then open `https://logia.onrender.com` (or the
   `onrender.com` address Render gives it) and check the site.
3. Under the service's **Settings > Custom Domains** you will see
   `logia.faith` and `www.logia.faith`. Render adds `www` and redirects it
   to the root.

Deploys run when CI passes on `main` (`autoDeployTrigger: checksPass`).

## 2. Point Cloudflare at it

In the Cloudflare dashboard for `logia.faith`:

1. **DNS > Records**: delete any existing `A`, `AAAA` or `CNAME` records for
   `logia.faith` (`@`) and `www`. Render has no IPv6, so no `AAAA` records
   should stay.
2. Add two records, both **DNS only** (grey cloud) for now:

   | Type  | Name  | Target                       | Proxy    |
   |-------|-------|------------------------------|----------|
   | CNAME | `@`   | `logia.onrender.com`         | DNS only |
   | CNAME | `www` | `logia.onrender.com`         | DNS only |

   Use the exact `onrender.com` address from step 1. Cloudflare flattens the
   root CNAME, so `@` is allowed.
3. **SSL/TLS > Overview**: set the encryption mode to **Full**.
4. Back on Render, click **Verify** next to each domain. Once both show a
   certificate as issued, `https://logia.faith` is live.
5. (Optional) Turn the two records to **Proxied** (orange cloud) for
   Cloudflare's cache and protection. Keep SSL/TLS on **Full**, because
   **Flexible** causes a redirect loop.

## If something goes wrong

- **Verification fails**: DNS hasn't spread yet. Wait a few minutes. Check
  with `dig +short logia.faith` and retry.
- **502 just after verifying**: Render is still updating its routing. Wait.
- **Too many redirects**: Cloudflare SSL is on Flexible. Set it to Full.
