# Front Range Fly Map

An interactive map of 26 fly-fishing spots within about an hour of Gunbarrel, CO, built from the
[Rocky Mountain Anglers](https://rockymtanglers.com/river-reports/) and
[Front Range Anglers](https://frontrangeanglers.com/pages/river-reports) river reports.

Pick a month to see which spots should be fishing and which flies to tie on. The basemap opens on
the USGS topo map (shaded relief); switch to USGS satellite from the map corner.

## How it stays current

Every day at 6 am Denver time, a GitHub Action runs `scripts/update.py`. It:

1. Reads each shop's report pages.
2. Pulls the report dates, Front Range Anglers' flow / water temp / clarity / guide rating, and both shops' fly lists.
3. Writes them to `data/live.json` and redeploys the site.

No AI or paid service is involved. If a shop page can't be read (site down, redesign), that shop
keeps its last good data and the run log says `KEPT`. The written "right now" tips on the map are
summaries from the October 2026 reports; once a shop posts a newer report, the map hides the old tip
and links to the new report instead.

## One-time setup (about 10 minutes, all in the browser)

1. **Create the repo.** Sign in to github.com, click **New repository**, name it
   `front-range-fly-map`, choose **Public**, and click **Create repository**.
2. **Upload the files.** On the new repo page click **uploading an existing file**, then drag in
   `index.html`, `README.md`, and the `data` and `scripts` folders. Click **Commit changes**.
3. **Add the updater.** Click **Add file → Create new file**. For the name, type
   `.github/workflows/update.yml` (the slashes create the folders). Paste in the contents of the
   `update.yml` file from this download and click **Commit changes**.
   *(Your computer hides folders that start with a dot, which is why this step is separate.)*
4. **Turn on the website.** Go to **Settings → Pages**. Under **Build and deployment → Source**,
   pick **GitHub Actions**.
5. **Run it once.** Go to the **Actions** tab, click **Update fishing reports**, then
   **Run workflow**. After about a minute it shows a green check.
6. **Open your site** at `https://YOUR-USERNAME.github.io/front-range-fly-map/` and send that link
   to anyone. It works in any phone, tablet, or computer browser with no sign-in.

### If something goes wrong

- **The run fails at "Save the new data" with a permission error:** Settings → Actions → General →
  Workflow permissions → choose **Read and write permissions** → Save, then run it again.
- **The run fails at "deploy":** check that step 4 is set to **GitHub Actions**.
- **The 6 am run starts a little late:** GitHub queues scheduled jobs, so runs often start 5–30
  minutes after the hour. To change the time, edit both `cron` lines and the matching times in the first step of
  `.github/workflows/update.yml`.
- **A shop shows `KEPT` in the log for weeks:** its page layout probably changed. The map keeps
  working with the last good data; the parser in `scripts/update.py` needs a tweak.
- **GitHub emails that the scheduled workflow was disabled:** GitHub pauses schedules on repos with
  no activity for 60 days. The updater commits on every run, so this shouldn't happen, but if it
  does, open the Actions tab and click **Enable workflow**.

## Files

| Path | What it is |
| --- | --- |
| `index.html` | The whole map: spots, fly lists, season logic, and styling |
| `data/live.json` | Latest report data, rewritten by the updater |
| `scripts/update.py` | The updater (Python, `requests` + `beautifulsoup4`) |
| `.github/workflows/update.yml` | The schedule that runs the updater and publishes the site |

Basemaps: USGS The National Map (public domain). Check CPW and National Park Service regulations before you fish.
