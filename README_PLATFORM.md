# Legacy API platform notes

The currently supported product entry point is the standalone Streamlit workspace in [app.py](README.md).

The API-backed implementation, browser consoles, Docker Compose stack, PostgreSQL/PostGIS migrations, and related deployment notes in this repository are retained as legacy development material. They are **not** started by the Streamlit application, are **not** required to run it, and are not connected to its workspace state.

For the supported experience:

1. Install the root dependencies with `pip install -r requirements.txt`.
2. Start the app with `streamlit run app.py`.
3. Use the sidebar to navigate the six workspace modules.
4. Use **Save workspace** and **Restore workspace** to carry editable state between sessions.

The standalone workspace does not ingest physical sensor telemetry, authenticate real operators or drivers, persist records to a server database, or provide turn-by-turn road routing. Do not interpret its workspace values or coordinate-based route estimates as verified field measurements.

See [README.md](README.md) for the supported product setup, deployment and test instructions.
