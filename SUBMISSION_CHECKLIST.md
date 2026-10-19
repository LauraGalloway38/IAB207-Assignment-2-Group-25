# NIGHTBITE submission checklist

Prepared against repository base `506be25` on 19 October 2026. This is a preparation checklist, not confirmation that the submission is complete.

## Evidence and limits

Repository backlog items specify these checks:

- [PB-077 / issue 77](https://github.com/LauraGalloway38/IAB207-Assignment-2-Group-25/issues/77): assignment declaration, member information, AI-use documentation and applicable signatures.
- [PB-078 / issue 78](https://github.com/LauraGalloway38/IAB207-Assignment-2-Group-25/issues/78): correct top-level structure, declaration, `main.py`, application package/resources, exclusions and successful extraction.
- [PB-079 / issue 79](https://github.com/LauraGalloway38/IAB207-Assignment-2-Group-25/issues/79): functional, database, Acknowledgement of Country, deployment, contribution and submission audit.
- [PB-076 / issue 76](https://github.com/LauraGalloway38/IAB207-Assignment-2-Group-25/issues/76): final source and contribution audit, including outstanding branches.
- [PB-080 / issue 80](https://github.com/LauraGalloway38/IAB207-Assignment-2-Group-25/issues/80): approved ZIP, deadline and submission receipt.

These are team backlog records, not the official brief. No assessment specification or declaration template was found in the current tracked files; the local synced `sources/` directory was empty. Exact naming, format, deadline and submission-channel requirements remain unverified.

## Proposed ZIP contents

Use the official top-level folder name once confirmed. Keep `main.py` beside the `nightbite/` folder.

| Include | Reason/status |
| --- | --- |
| `main.py`, complete `nightbite/` source/templates/static assets | Required application structure identified by PB-078 |
| `requirements.txt` | Reproducible dependency installation |
| `README.md` | Setup, configuration and verification instructions |
| Completed official assignment declaration | Required by PB-077; missing |
| Completed AI-use documentation in required format | Draft `AI_DECLARATION.md` supplied; member confirmation pending |
| `tests/`, `evaluate_ai_search.py` | Recommended verification evidence/tools; mandatory status unconfirmed |
| `requirements-ai-installed.txt` | Existing dependency inventory; retain as reference |
| `SUBMISSION_CHECKLIST.md` | Working audit record; inclusion optional unless required |
| Approved synthetic database and matching uploads, if required | Requirement unverified; otherwise regenerate demo data using README |
| Deployment link, Scrum logs, contribution/report evidence, if required | Confirm whether these belong in the ZIP or separate submissions |

Exclude `.git/`, `.venv/`, `venv/`, caches, `.DS_Store`, editor settings, `.env`, `instance/secret-key`, private data and unrelated Assignment 1 files. Do not blindly ZIP the entire working directory.

After committing the final approved files, a tracked-source starting archive can be made with:

```sh
git archive --format=zip --prefix=NIGHTBITE-Group25/ --output=../NIGHTBITE-Group25-source.zip HEAD
```

The prefix and filename above are provisional. Git archive excludes untracked/ignored files, including databases and uploaded images. Add the completed official declaration and any required approved data/resources before calling an archive final. Verify that no private material was tracked before archiving.

## Remaining checks

- [ ] Obtain/check the current Assignment 2 brief and exact archive/folder names, deadline, size limits and submission channel.
- [ ] Confirm the required official declaration template, format, all member names/student numbers and applicable signatures.
- [ ] Complete each member's AI record and required evidence; this task cannot attest to unreported use.
- [ ] Confirm final merges, branch selection and contribution evidence with the team.
- [ ] Confirm deployed URL, synthetic production data and working read/write flows (PB-074 and PB-079).
- [ ] Confirm whether a database, uploads, report, Scrum evidence or separate individual submissions are mandatory.
- [ ] Run a clean dependency installation and full pytest suite; record Python/package versions and actual results.
- [ ] Check real-model search separately from mocked tests and verify offline/failure behaviour.
- [ ] Extract the candidate ZIP and follow the README from a clean directory.
- [ ] Test the complete user journeys and enhanced Acknowledgement of Country custom text against the current brief.
- [ ] Obtain team approval, submit the intended final archive and retain its receipt.

## Verification record for this preparation

Current source, setup commands, configuration paths, seed logic, AI imports and test collection style were inspected. An automated-test attempt could not start because this checkout has no `.venv/bin/python`; no passing test result or fresh-install compatibility is claimed. No final ZIP, deployment or submission has been certified by this documentation change.
