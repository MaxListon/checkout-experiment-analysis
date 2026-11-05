# Put this project on GitHub and your resume

Everything in this folder belongs to the project. The companion ZIP places these files at its top level, ready to copy into an empty GitHub repository.

## Suggested GitHub repository

- **Repository name:** `checkout-experiment-analysis`
- **Description:** `Reproducible SQL and Python analysis of a simulated checkout experiment, with conversion, revenue, refund safety and launch planning.`
- **Topics:** `sql`, `python`, `product-analytics`, `experimentation`, `a-b-testing`, `sqlite`, `statistics`
- **Visibility:** Public if you are comfortable sharing your portfolio. The included data are synthetic. Review every file before making it public.

Keep the repository structure at its root:

```text
README.md
GITHUB_GUIDE.md
readout.html
experiment-readout.pdf
analysis.ipynb
config.json
requirements.txt
data/
sql/
src/
tests/
results/
charts/
docs/
```

Start with the project `README.md` as the repository landing page. It links to the executive brief, case study, notebook and reproduction steps. Keep the synthetic-data disclosure visible. The SQLite database is included so a reviewer can query it immediately; the CSV source tables make the example auditable.

The GitHub repository should contain this project's files, not the surrounding Codex workspace or generated ZIP. Do not add virtual environments, caches, `.DS_Store`, or unrelated personal files. `.gitignore` already excludes common local development files.

## Upload steps

1. Download `checkout-experiment-portfolio.zip` and extract its contents into a new folder named `checkout-experiment-analysis`. The README and `src/` should be directly inside that folder, not inside another nested `checkout-experiment/` folder.
2. Create a new **empty** GitHub repository named `checkout-experiment-analysis`. Do not add an auto-generated README; this project already has one.
3. In Terminal, change into the extracted folder. Replace `<YOUR-GITHUB-URL>` below with the remote URL GitHub gives you:

```sh
git init
git add .
git commit -m "Add checkout experiment analysis portfolio project"
git branch -M main
git remote add origin <YOUR-GITHUB-URL>
git push -u origin main
```

4. Open the repository page and confirm that `README.md` renders at the top level. Follow the brief, HTML case study and executed notebook links. Check the archive's files are present before sharing the repository URL with an employer.

If you prefer GitHub Desktop, add the extracted folder as a local repository, commit it, then publish that repository to your GitHub account. Keep the remote private until you have reviewed the visible files and synthetic-data disclosures.

## Resume bullet options

Choose one version that fits your experience. Keep the word **simulated** so the project is not mistaken for a real retailer's experiment.

**SQL and analytics:**

> Built a reproducible SQL and Python analysis of a simulated 24,000-user checkout experiment; retained all assigned users, modeled purchase and refund windows, and quantified conversion, revenue and refund uncertainty.

**Experimentation and decision-making:**

> Evaluated a simulated 24,000-user checkout test using Wilson/Newcombe confidence intervals and 10,000 user-level revenue bootstrap resamples; recommended further testing only if revenue-safety precision is economically feasible.

**Data quality and pipeline work:**

> Developed a SQLite/Python pipeline for a simulated checkout experiment, with assignment-conflict checks, duplicate-ingestion handling, refund-safe aggregation, and independent user-level SQL reconciliation.

Do not describe the +0.59 percentage-point conversion estimate as a proven business lift. It is an uncertain result from synthetic data. Avoid claims of revenue growth, production impact or real-world savings.

## Repository About and interview summary

Use the description above in GitHub's short **About** field. If someone asks what the repository demonstrates, a concise answer is:

> I created synthetic randomized experiment data so I could show the full analyst workflow: define the user-level outcome, build a trustworthy SQL dataset, estimate effects and uncertainty in Python, then make a launch recommendation that accounts for revenue, refunds and the cost of learning more.

Practice explaining the join order, nonbuyer denominator, interpretation of the confidence interval, and why the sample size for revenue safety is much larger than the conversion-only requirement. The [interview guide](docs/INTERVIEW_GUIDE.md) has a longer walkthrough and common follow-up questions.

## Before sharing

- Keep the simulated-data label on the README, brief, case study and resume bullet.
- Check that your GitHub repository uses a visible README and that its project links work.
- Review the resume wording and remove any technique you cannot explain in an interview.
- A public repository has no license by default. Add a license only after deciding how you want others to be allowed to reuse your code.
- Include a portfolio or project link with the resume bullet only after the GitHub repository is published and checked.
