# uattriage

> UAT analytics that answer 'are we ready to go live' with a projected date and an uncertainty band, not a defect count.

`COMPACT` · **Business Analyst** · Intermediate · ~4-5 days · Public sector - benefits system replacement

**Primary language:** Python
**Tags:** `reliability-growth`, `uat`, `quality`, `forecasting`, `reporting`

---

## The problem

UAT produces 600 defects in three weeks. The project manager asks whether the system is ready to go live. Answering honestly requires knowing whether the arrival rate is falling, whether severity is shifting, and whether defects cluster in one module - none of which a defect count answers, so the decision gets made on confidence instead.

## ⭐ The differentiator

Fits a **defect-discovery (reliability growth) curve to estimate remaining latent defects and a projected date-to-threshold with an uncertainty band** - turning '600 open defects' into 'we project 80-140 undiscovered defects remain; readiness at the agreed severity threshold is 9-17 days away'. A generic UAT dashboard shows open and closed counts by severity and provides no basis at all for the decision actually being made.

This is the sentence to lead with when someone asks you to walk through the
project. Everything else in this repo exists to make it true and to prove it.

## Data

A synthetic defect-arrival generator following documented reliability-growth models with **known latent-defect counts**, validated against public defect datasets from the PROMISE repository.

> No paid API key is required to run or demo this project. Where a paid
> service would add value it is wired as an optional enhancement behind an
> interface with an offline mock as the default implementation.

## Stack

- Python with SciPy for curve fitting
- DuckDB, Plotly
- Quarto for the readiness report
- pytest

## Core capabilities

- Defect arrival and closure curves by severity and module
- Reliability-growth fit (Goel-Okumoto and S-shaped) with model comparison and confidence intervals
- Module clustering identifying concentration of severity-1 defects
- Reopen-rate analysis distinguishing 'fixed' from 'closed'
- Readiness report stating the decision rule and its uncertainty explicitly

## Repository layout

```
src/models/
src/report/
generator/
test/
report/
```

## Build plan

1. Generator with a known latent-defect count. The whole project hinges on being able to check the estimate.
2. Fit and compare models. Report the comparison - picking one silently is how these estimates get trusted too much.
3. Calibration test across many runs. One lucky fit is not evidence.
4. Report last, written for a project manager rather than a statistician.

## Testing strategy

Assert the fitted latent-defect estimate **covers the generator's true value at the stated confidence level across 200 simulated runs** - this is a calibration test, not a single lucky fit. A model that is right once and overconfident in general is worse than no model.

Tests assert **correctness**, not merely that the code runs. A green suite on
this repo is a claim about behaviour under adversarial conditions; treat any
test that would pass against a deliberately broken implementation as a bug in
the test.

## Quality & safety layer

The report states its assumptions (constant test effort, stable scope) and flags when the observed data violate them, rather than projecting regardless.

## Measurable outcome

> A one-page readiness report giving a projected go-live window of 9-17 days with its confidence band, replacing a defect count that could not support the decision.

State it in these terms — business units, not technical ones — in your CV
bullet and in the first thirty seconds of describing the project.

## Interview questions this project answers

- **How do you know when testing is finished?**
- **What assumptions does a reliability-growth model make, and when do they break?**
- **Why report an interval rather than a date?**

## What this deliberately is *not*

- Not a defect tracker. It reads yours.
- Not a guarantee - it is a calibrated projection, and the report says so.


## Run it now

```bash
python -m unittest discover -s tests -v   # the suite
python -m src.demo                        # the 60-second artefact
```

Requires Python 3.11+. The runnable core uses **only the standard
library** (including `sqlite3`), so there is nothing to install.

## Getting started

```bash
git clone <your-fork-url> uattriage
cd uattriage
pip install -e .
python -m generator --weeks 3
python -m src.models fit --compare
quarto render report/readiness.qmd
pytest test/test_calibration.py
```

Docker is supported but optional — every path above works on a plain
Windows/macOS/Linux laptop without a cloud account.

## Definition of done

- [ ] The differentiator above is implemented, and a test proves it
- [ ] The measurable outcome is produced by a command anyone can run
- [ ] `README` explains the one decision a generic version gets wrong
- [ ] CI runs the full suite on every push and is green on `main`
- [ ] A recruiter can see the headline artefact in under 60 seconds

## Licence

MIT — see [LICENSE](LICENSE).
