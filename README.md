
# WellAtlas V4 Demo (Scheduling & Job Gantt)

This demo build gives you:

- Gold-on-flag UI using your waving flag as background (static/img/wallpaper.jpg).
- Map-based homepage (Leaflet + MapTiler hybrid).
- Customers → Sites → Jobs drilldown.
- Calendar view grouped by job start date.
- Job-only Gantt (single bar, start→end, status-aware).

## Env Vars

- `MAPTILER_KEY` – your MapTiler API key for the hybrid tiles.

## Run Locally

```bash
pip install -r requirements.txt
export MAPTILER_KEY=YOUR_MAPTILER_API_KEY
python app.py
```

Then open: http://localhost:5000/

## Deploy to Render

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Env var: `MAPTILER_KEY` set to your key.
