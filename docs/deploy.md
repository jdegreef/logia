# Deploying logia.faith

The site is static: Render runs `python3 scripts/build_site.py` and serves
`site/`. `render.yaml` holds the settings. DNS is on Cloudflare.

The build's one dependency is [Pagefind](https://pagefind.app), which indexes
the words of every excerpt for `/search/` into `site/pagefind/`. The build
command installs it, pinned (`pagefind[bin]==1.5.2` and `pagefind-bin==1.5.2`),
and CI does the same. Without it the site still builds, and `/search/` says the
words can't be searched in that build. To build with search locally:

    python3 -m pip install 'pagefind[bin]==1.5.2' 'pagefind-bin==1.5.2'
    python3 scripts/build_site.py

## 1. Create the site on Render

1. Render Dashboard > **New** > **Blueprint**, pick `jdegreef/logia`, branch
   `main`, and apply. This creates the static site `logia`.
2. Wait for the first deploy, and note the service's `onrender.com` address
   (Settings > Custom Domains > Render Subdomain; Logia's is
   `logia-nw2v.onrender.com`). The site is not served there
   (`renderSubdomainPolicy: disabled`), but it is the DNS target below.
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
   | CNAME | `@`   | `logia-nw2v.onrender.com`    | DNS only |
   | CNAME | `www` | `logia-nw2v.onrender.com`    | DNS only |

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

## 3. Visit counts and search engines (optional)

Each of these is off until its environment variable is set on the Render
service (**Environment > Environment Variables**). A change takes effect on
the next deploy, so after saving, run **Manual Deploy > Deploy latest
commit**.

| Variable              | Value                                   | Turns on |
|-----------------------|-----------------------------------------|----------|
| `LOGIA_GOATCOUNTER`   | the GoatCounter site code, e.g. `logia` | GoatCounter's counter on every indexed page, and a line on the About page saying so |
| `LOGIA_GOOGLE_VERIFY` | the code from Search Console's *HTML tag* method | `<meta name="google-site-verification">` |
| `LOGIA_BING_VERIFY`   | the code from Bing Webmaster Tools' *meta tag* method | `<meta name="msvalidate.01">` |

**GoatCounter**: sign up at goatcounter.com (free for non-commercial sites)
and choose the code; the dashboard is then at `https://<code>.goatcounter.com`.
GoatCounter sets no cookies and keeps no IP addresses, so no consent banner
is needed.

**Search Console**: add `https://logia.faith/` as a *URL prefix* property,
pick *HTML tag*, and copy only the `content` value. Once verified, submit
`https://logia.faith/sitemap.xml` under *Sitemaps*. Bing Webmaster Tools can
import the site from Search Console instead of using its own code.
