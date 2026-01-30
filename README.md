# Project Repository

## Pytest HTML report (self-contained)

Generate a self-contained pytest HTML report with:

```bash
python -m pytest --html=pytest_report.html --self-contained-html
```

Note: `--self-contained-html` ensures the report does not import external stylesheets. The exact look-and-feel is controlled by pytest-html itself.
