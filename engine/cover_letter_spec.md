# Cover letter spec

This is the standing brief for whoever writes the letter body (you, or your AI
assistant). `build_application.py` only handles the header, date, recipient block,
greeting and closing. **You write the BODY paragraphs**, save them to a `.txt`
file (one paragraph per block, blank line between), and pass that file to the script.

Before writing, read:
- `profile/facts.md` — the facts you are allowed to use (copy `facts.example.md`).
- `profile/writing_style.md` — how you sound (optional; copy `writing_style.example.md`).
- `master/` — your resume, the final word on what is true.

## Company-level and reusable (important)

Letters are written **about the company, not one specific posting**, so a single
letter can be reused across every role you flag at that company (e.g. one letter
for all five roles you marked Interested at the same firm). Therefore:

- Speak to the company, its business and space, and why you fit *there* — not to
  a single job title or its bullet points.
- Keep it broad enough to send for any role you flagged at that firm without edits.
- Only write a job-specific letter when explicitly asked (`make-job`); then you may
  reference that exact role and its requirements.
- One letter per company. `pending` shows which companies still need one.

## Voice and tone

- Professional, warm, earnest. Confident but humble; never arrogant, never generic.
- First person, sincere. Follow `profile/writing_style.md` if it exists, but keep it
  cleaner than personal essays.
- **No fabrication.** Only use facts from `profile/facts.md` and the resume. If a
  claim isn't supported there, leave it out.
- Mention work authorization only if a posting specifically asks.

## Structure (4 short paragraphs, ~250–320 words)

1. **Opening** — the company (and the role, for a job-specific letter) and one crisp
   line on why you.
2. **Academic fit** — degree, standing, the coursework and skills that map to what
   this company does. Credentials and awards where relevant.
3. **Experience fit** — tie one or two concrete accomplishments (with numbers) to
   what the company needs.
4. **Close** — enthusiasm for this company specifically and a polite call to talk.

## Tailoring rules

- Pull 2–3 concrete themes from the company's roles and descriptions
  (`company-context`) and reflect them back honestly, only where you truly match.
- One page. Plain, confident sentences. No buzzword salad.
- Greeting defaults to "Dear Hiring Manager,".

## What the script adds automatically (don't write these)

Header (name, city, phone, email, LinkedIn/portfolio from `config/config.yaml`),
the date, the recipient block, the greeting, and the "Sincerely, / <your name>" close.
