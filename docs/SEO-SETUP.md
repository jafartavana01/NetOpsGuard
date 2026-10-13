# NetOpsGuard discoverability and search indexing setup

This is a maintainer checklist. **Adding documentation does not automatically enable GitHub Pages, update repository metadata, or guarantee indexing.** Complete these GitHub settings after merging the documentation pull request.

## 1. Fill in the GitHub repository About section

Go to **https://github.com/jafartavana01/NetOpsGuard**, open the **About** section's gear/edit control, and set:

**Description (copy exactly):**

> Self-hosted TACACS+ AAA, Cisco command authorization, RADIUS, AD/LDAP, network configuration backup (NCM) and security auditing.

**Website** (only after GitHub Pages is published successfully):

`https://jafartavana01.github.io/NetOpsGuard/`

**Topics** (select relevant existing suggestions or add these valid, concise tags; GitHub allows up to 20):

```text
tacacs, tacacs-plus, tacacs-server, aaa, radius, network-security, network-automation, network-configuration-management, network-access-control, cisco, ios-xe, active-directory, ldap, command-authorization, ncm, netops, security-auditing
```

Keep all topics relevant to actually supported features. Do not use broad or misleading tags to chase traffic.

## 2. Publish the public documentation site with GitHub Pages

The repository contains a Jekyll site in **docs/**, including a public landing page, topic-specific guides, page descriptions, canonical URLs, Open Graph metadata, and a sitemap plugin.

After the PR is **merged to main**:

1. Open **Settings → Pages** in this repository.
2. Under **Build and deployment**, select **Deploy from a branch**.
3. Set branch to **main** and folder to **/docs**, then save.
4. Review the Pages build/deployment in **Actions** and verify the published site, its navigation, and its sitemap.
5. Open `https://jafartavana01.github.io/NetOpsGuard/` and verify it serves the new homepage rather than an error before putting it in the repository's Website field.

Do not configure an unowned custom domain or point DNS at GitHub Pages before adding and verifying the domain in GitHub Pages settings.

## 3. Confirm canonical URLs, metadata, and sitemap

Inspect the published HTML source. Each documentation page should have a unique title, meta description, canonical URL, and social metadata. The homepage also includes a SoftwareApplication JSON-LD description, accurately reflecting the five-device Community edition.

When the Jekyll sitemap plugin is available and the build has succeeded, check:

`https://jafartavana01.github.io/NetOpsGuard/sitemap.xml`

If Pages or Jekyll fails to build, use the **Actions** deployment logs; do not announce a public website before it is available.

## 4. Request search indexing

After Pages is live, create a **Google Search Console** URL-prefix property for:

`https://jafartavana01.github.io/NetOpsGuard/`

Verify site ownership using an available Search Console method. If an HTML verification file is issued, commit the **exact unique file** under `docs/`, merge it, and validate ownership. Do not invent a verification code.

Submit the sitemap URL from step 3 and use URL Inspection for important landing and guide URLs. Search indexing is at Google's discretion and can take time; no tool can guarantee a position or inclusion in results. Consider Bing Webmaster Tools after verifying the public site.

## 5. Improve GitHub link previews

Open **Settings → Social preview** and upload a legible, branded image (GitHub recommends **1280 × 640 pixels**, PNG/JPEG/GIF, under **1 MB**). A clear project name and short TACACS+/AAA description are more useful than a dense screenshot.

## 6. Prefer Pages over a Wiki for SEO

A separate Wiki duplicates documentation effort and is not the best search-oriented source. GitHub documents that Wiki indexing is restricted for repositories with fewer than **500 stars**. Maintain the canonical public guides in **docs/** and GitHub Pages. Only add a Wiki later if a community editing workflow warrants it.

## 7. Keep discovery information current

Update the repository description/topics when capabilities truly ship, publish useful feature-specific technical articles, and link the documentation site from related public profiles, release announcements, and relevant technical content. Avoid duplicate, keyword-stuffed pages or unsupported release claims.

### Current limitations

Repository About, topics, website, Social preview, Pages publishing, and Search Console verification are **GitHub/account settings or external services**, not files that commit automatically. Until changed in those systems, the repository may still have empty metadata and no published documentation site.

References: [GitHub Pages publishing](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site), [GitHub repository topics](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics), [GitHub wiki indexing](https://docs.github.com/en/communities/documenting-your-project-with-wikis/about-wikis), [Google SEO](https://developers.google.com/search/docs/fundamentals/seo-starter-guide).
