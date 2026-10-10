# Python Automation & API QA — Independent Work Samples

Small, practical Python projects with reproducible tests and direct source links. **Independent demos only:** not prior paid customer work, reviews or client testimonials.

**Services (proposed starting prices):**
- Python / REST API bug fixes + regression tests: **$49–149**
- CSV/JSON/API workflow automation: **$79–189**
- Python unit testing + QA notes: **$39–129**

Most work can be scoped and delivered through **written/asynchronous communication**. AI coding tools may be used where the client and platform permit them; deliverables are still reviewed and tested.

## Demos

| Example | Features | Proof |
|---|---|---|
| [Python token bucket](demo/token_bucket/rate_limiter.py) | Configurable requests/sec and burst, thread safety, no dependencies | [15 deterministic tests](demo/token_bucket/test_rate_limiter.py) |
| [CSV normalizer](demo/csv_cleanup/csv_cleanup.py) | Safe local CSV data cleanup, deterministic dedupe, input validation, CLI | [7 tests](demo/csv_cleanup/test_csv_cleanup.py) |

```bash
cd demo/token_bucket && python3 -m unittest -v test_rate_limiter.py
cd ../csv_cleanup && python3 -m unittest -v test_csv_cleanup.py
```

[View the portfolio website](https://tanhaien.github.io/aki-python-automation-portfolio/) · [GitHub profile](https://github.com/tanhaien)

## Fixed-scope packages

### Python bug fix — $49 starter
One reproducible bug, one regression test, a short patch and README. Delivery estimate: 2 business days after requirements. Standard and larger packages quoted by scope.

### Python workflow automation — $79 starter
One data-to-output Python workflow with sample inputs and three tests. API access must be authorized by the buyer, and no passwords or tokens are stored in this repo.

### Python QA / unit tests — $39 starter
One small Python module, up to five deterministic unit tests, test command and a short QA note.

**Not included:** paid API subscriptions, unauthorized web scraping, live cloud deployment, guaranteed uptime, transaction signing, security penetration tests, broad application rewrites, or 24/7 support.

Client source materials stay private. Samples are MIT licensed; no customer material is published.

## Contact and scope

[Open a GitHub issue](https://github.com/tanhaien/aki-python-automation-portfolio/issues/new?template=service_quote.yml) with non-sensitive requirements, or contact via an authorized freelancer platform. Please describe the expected input/output, runtime, scope and deadline. **Do not post credentials or proprietary files in a public issue.**

**Status:** This is a public technical portfolio and price menu; it is not a registered Upwork/Contra/Fiverr catalog or evidence of any contracted work.
