"""Live Google Sheets personal-finance dashboard.

Module map:

- ``sheets_client`` -- the Google Sheets API wrapper (the only module that talks
  to the network)
- ``userconfig`` -- loads the gitignored ``config.py`` from the project root
- ``schema`` -- describes how a sheet is *shaped* (block vs flat layout)
- ``data`` -- parses a sheet into the one tidy table everything else builds on:
  ``year | month | date | category | amount | comment | is_income | month_str``
- ``analytics`` -- pure pandas over that table; no Streamlit, so it is testable
- ``sample_data`` -- synthetic transactions for demo mode
- ``app`` -- the Streamlit UI
- ``validate`` / ``inspect_sheet`` -- command-line helpers
"""
