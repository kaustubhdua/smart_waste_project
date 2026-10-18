# Device, telemetry import, model and driver setup

## 1. Start the platform

Copy .env.example to .env, replace both placeholder secrets with unique random values, and run:

    docker compose up --build

Open the operator console at http://localhost:8080 and API docs at http://localhost:8000/docs.

## 2. Register a bin and sensor

Register a bin in the operator console. Use Enroll a sensor device to create a device ID bound to that bin. The returned token is shown once; store it in the sensor's secure configuration. The database stores only a SHA-256 hash. Device tokens can be rotated or revoked.

Send a live reading to POST /api/v1/telemetry with the per-device X-Device-Token header. The JSON body needs bin_id, device_id, a unique message_id, fill_percent and a timezone-aware measured_at. temperature_c is optional for telemetry storage but required for the current ML model.

Example payload:

    {"bin_id":"BIN-001","device_id":"SENSOR-001","message_id":"boot-7-seq-104","fill_percent":63.2,"temperature_c":25.4,"measured_at":"2026-10-18T10:30:00Z"}

Message IDs are idempotent only when a repeated payload matches. A device is authorized for one bin. Future timestamps beyond the configured clock-skew allowance are rejected.

## 3. Import historical telemetry

POST /api/v1/telemetry/import-csv accepts multipart field file and these required CSV columns:

    bin_id,device_id,message_id,fill_percent,measured_at
    BIN-001,public-dataset,record-001,63.2,2026-10-18T10:30:00Z

temperature_c is an optional extra column. Uploads are limited to 2 MB and 10,000 rows. The endpoint validates the entire batch before committing it; imported rows are labeled source=imported.

## 4. Train and inspect the ML model

From the repository root, install requirements.txt and run:

    python person2_ml_prediction.py

The model artifact is written to models/waste_model.pkl and mounted read-only into the API container. Restart the API after training. The forecast endpoint requires recent telemetry, a temperature measurement and enough history. It predicts the next observed fill value; it is not a validated six- or twelve-hour forecast. Keep USE_MODEL_FOR_DISPATCH=false until you evaluate model quality on representative real data.

## 5. Create jobs, dispatch and collect

Select bins in the operator console and create jobs from fresh telemetry. Approve jobs, register vehicles, then select approved jobs and click Optimize and dispatch approved jobs. The planner uses the OSRM road matrix and OR-Tools capacity constraints; selected vehicles must share a depot.

Enroll a driver against a vehicle in the operator console. Open http://localhost:8080/driver.html, enter the Driver ID and one-time token, load assigned stops, start each stop, then mark it collected or report an exception. The driver view is online-only and hands navigation off to an external map app; it does not offer offline action queues or embedded turn-by-turn directions.

## Production boundary

This repository now supports a real software workflow, but physical sensor calibration, device clock synchronization, production identity/RBAC, TLS and secret management, OSRM service guarantees, database backups, load testing and a municipal field pilot still require separate work and evidence.