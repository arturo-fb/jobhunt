# JobHunt command cheatsheet

Run everything from the project folder (`cd ~/jobhunt`).

## Everyday

| Do this | Command |
|---|---|
| Run a scan now | `python3 engine/jobhunt.py` |
| Refresh the **Applied** sheet after marking jobs Applied (no scan) | `python3 engine/jobhunt.py --sync` |
| Try it with bundled sample data (no internet or keys) | `python3 engine/jobhunt.py --sample` |

## Cover letters

One reusable letter per company. Easiest: tell your AI assistant **"make my cover letters"**
(see `prompts/daily_review.md`). By hand:

| Do this | Command |
|---|---|
| List today's New jobs | `python3 engine/build_application.py new-today` |
| Mark jobs as Suggested | `python3 engine/build_application.py suggest <JOB_ID> <JOB_ID> ...` |
| Companies still waiting for a letter | `python3 engine/build_application.py pending` |
| Full detail on one job | `python3 engine/build_application.py context <JOB_ID>` |
| All flagged roles + details for a company | `python3 engine/build_application.py company-context "<COMPANY>"` |
| Build ONE reusable company letter | `python3 engine/build_application.py make-company body.txt "<COMPANY>"` |
| Build a job-specific letter | `python3 engine/build_application.py make-job <JOB_ID> body.txt` |

Letters land in `Applications/<Company>/` as `<YourName>.CL.pdf` and an editable
`<YourName>.CL.###.docx`. Send them with your resume from `master/`.

## Scheduler

| Do this | Command |
|---|---|
| Install the daily scan (6 AM) | `./engine/install_schedule.sh` |
| Another hour | `./engine/install_schedule.sh --hour 7` |
| Pause it (nothing is deleted) | `./engine/install_schedule.sh --uninstall` |
| Is it installed? (macOS) | `launchctl list \| grep jobhunt` (`0` = healthy) |
| Run it right now (macOS) | `launchctl start com.jobhunt.daily` |

You never run `engine/run_scan.sh` yourself; the scheduler calls it. To pause the
morning AI review too, turn that scheduled task off in your AI tool.

## Troubleshooting

| Check | Command |
|---|---|
| Scan history | `tail -n 20 data/run_log.txt` |
| Scheduler errors (macOS) | `cat data/launchd.log` |
| When was the last scan? | `cat data/last_scan.json` |

On macOS, exit code **78** or "Operation not permitted" means the project sits in a
privacy-protected folder (`Documents`, `Desktop`, `Downloads`). Move it to your home
folder and run `./engine/install_schedule.sh` again.

## Status values (Jobs sheet)

| Value | Meaning |
|---|---|
| **New** | Found in the most recent scan |
| **Old** | Seen in an earlier scan, not acted on |
| **Suggested** | The AI review's top-5 pick of the day |
| **Interested** | You want it → a cover letter gets written for its company |
| **Applied** | You applied → it moves to the Applied sheet |
| **Not interested** | Dismissed |

Found and applied to something on your own? Add a row to the **Applied** sheet
(Date Applied, Company, Title, leave Job ID blank). Scans keep manual rows.

## Where things live

```
config/config.yaml     roles, locations, weights, profile, standard answers   (yours, git-ignored)
config/secrets.yaml    API keys                                               (yours, git-ignored)
config/companies.yaml  Greenhouse / Lever / Ashby boards to scan
profile/facts.md       facts cover letters may use                            (yours, git-ignored)
JobHunt.xlsx           your cockpit: Jobs / Applied / Config                  (created by the first scan)
Applications/          generated cover letters, one folder per company
master/                your resume
data/                  logs, caches, running document number
```
