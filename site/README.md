# Site generator

Static site for GitHub Pages. Builds from committed CSVs only (no LL2 API calls).

```bash
pip install -e ".[dev]"
python site/build.py                 # → site/_site/
python site/build.py --base-path ""  # local preview without /launch-delay-watch prefix
```

Deployed by `.github/workflows/pages.yml` via `actions/deploy-pages`.
