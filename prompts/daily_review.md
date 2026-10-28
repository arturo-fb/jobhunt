# Daily review prompt (for an AI scheduled task)

The scan runs on your computer every morning (see `engine/install_schedule.sh`). This
prompt is the second half: an AI assistant reviews what the scan found, flags the five
best new roles, writes the cover letters you asked for, and sends you a short message.

Any assistant that can run on a schedule and read and write files on your computer
works, for example Claude with scheduled tasks and folder access, or Claude Code.

## Setup

1. Finish the setup in the README (config, resume, `profile/facts.md`), and install the
   daily scan.
2. Create a scheduled task that fires **about an hour after** the scan (scan at 6:00 →
   review at 7:00), with access to this repository's folder.
3. Paste everything under "The prompt" as the task's instructions and replace
   `<REPO_PATH>` with the full path to your copy of this repository.

You can also paste it into a normal chat any time to run the review on demand.

---

## The prompt

```text
Daily job-application review. The project lives at <REPO_PATH>. Work only inside that
folder. If you cannot access it, stop and say the folder needs to be reconnected.

Do NOT run a job scan; the scan runs on my computer every morning. You only read the
already-scanned JobHunt.xlsx and write cover letters. Never submit applications.

Who I am and what I want: read config/config.yaml (profile, search titles, locations,
seniority) and profile/facts.md. Use them to judge fit.

STEP 1 - cover letters for companies I marked "Interested":
  a. Run: python3 engine/build_application.py pending
  b. For EACH company listed:
     - First read engine/cover_letter_spec.md, profile/facts.md, and
       profile/writing_style.md if it exists. Letters are COMPANY-LEVEL and reusable.
       Use no facts beyond profile/facts.md and the resume in master/.
     - Run: python3 engine/build_application.py company-context "<COMPANY>"
     - Write ONE company-level letter body (paragraphs separated by blank lines) to
       data/_body.txt, following the spec.
     - Run: python3 engine/build_application.py make-company data/_body.txt "<COMPANY>"
     One letter per company, linked to all its Interested roles.
  If pending shows none, skip this step.

STEP 2 - is there anything new?
  a. Run: python3 engine/build_application.py new-today
  b. If it says "NO NEW JOBS TODAY": don't analyze or re-suggest anything. Send me a
     short message saying there are no new jobs today, include the latest Date Found it
     shows (so I know whether the morning scan ran), mention any letters from Step 1,
     and stop.
  c. Otherwise continue.

STEP 3 - suggest the 5 best NEW roles:
  a. Judge each new job against my profile (fit, location priority, level). Use
     data/descriptions.json for detail if helpful.
  b. Run: python3 engine/build_application.py suggest <JOB_ID> <JOB_ID> ...
     with the 5 strongest (fewer if fewer exist).
  c. Message me, concise and friendly: the number of new jobs today; the 5 you marked
     "Suggested" (Company - Title + a one-line reason each); any companies you wrote
     letters for in Step 1; then: "Open JobHunt.xlsx, set any Suggested role (or your
     own picks) to Interested and save. I'll write one reusable letter per Interested
     company on the next run, or tell me 'make my cover letters' to do it now."

Only mark jobs "Suggested" when they were genuinely added in today's scan.
```
