
import csv
import io
import os
import sqlite3
import random
from contextlib import contextmanager
from datetime import datetime, timezone

import boto3
from flask import Flask, Response, jsonify, render_template_string

import lambda_function


app = Flask(__name__)
DATABASE = os.environ.get(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(__file__), "smart_agriculture.db")
)


@contextmanager
def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                soil_moisture REAL NOT NULL,
                temperature REAL NOT NULL,
                humidity REAL NOT NULL,
                recommendation TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)


def analyze_values(soil_moisture, temperature, humidity):
    event = {
        "soil_moisture": soil_moisture,
        "temperature": temperature,
        "humidity": humidity
    }

    result = lambda_function.lambda_handler(event, None)

    if result["statusCode"] != 200:
        raise ValueError("The sensor values could not be analyzed.")

    import json
    return json.loads(result["body"])


def generate_sensor_reading():
    reading = {
        "soil_moisture": round(random.uniform(15, 75), 1),
        "temperature": round(random.uniform(18, 36), 1),
        "humidity": round(random.uniform(30, 85), 1)
    }

    analysis = analyze_values(
        reading["soil_moisture"],
        reading["temperature"],
        reading["humidity"]
    )

    reading["recommendation"] = analysis["recommendation"]
    reading["timestamp"] = datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )

    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO sensor_readings (
                soil_moisture, temperature, humidity,
                recommendation, timestamp
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            reading["soil_moisture"],
            reading["temperature"],
            reading["humidity"],
            reading["recommendation"],
            reading["timestamp"]
        ))

        reading["id"] = cursor.lastrowid

    return reading


DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Smart Agriculture Monitoring</title>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #f3f6f4;
            color: #203329;
        }
        header {
            background: #185c3b;
            color: white;
            padding: 25px 6%;
        }
        header h1 { margin: 0 0 8px; }
        header p { margin: 0; opacity: .9; }
        main { max-width: 1100px; margin: 28px auto; padding: 0 18px; }
        .notice {
            background: #fff8df;
            border: 1px solid #ead68b;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 20px;
        }
        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 16px;
        }
        .card, .panel {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 8px #0000000b;
        }
        .card h3 { margin-top: 0; color: #557064; font-size: 15px; }
        .value { font-size: 30px; font-weight: bold; color: #185c3b; }
        .panel { margin-top: 22px; }
        .panel h2 { margin-top: 0; }
        .buttons { display: flex; flex-wrap: wrap; gap: 10px; margin: 18px 0; }
        button, .button-link {
            border: 0;
            border-radius: 6px;
            background: #185c3b;
            color: white;
            padding: 11px 15px;
            cursor: pointer;
            text-decoration: none;
            font-size: 14px;
        }
        button.secondary { background: #3d6176; }
        button.optional { background: #777; }
        button:disabled { opacity: .55; cursor: wait; }
        #status { min-height: 24px; margin: 12px 0; }
        .table-wrap { overflow-x: auto; }
        table { border-collapse: collapse; width: 100%; min-width: 650px; }
        th, td { text-align: left; padding: 11px; border-bottom: 1px solid #e5eae7; }
        th { background: #edf3ef; }
        footer { text-align: center; color: #66766d; padding: 25px; font-size: 13px; }
    </style>
</head>
<body>
<header>
    <h1>Smart Agriculture Monitoring</h1>
    <p>Cloud-Based Smart Agriculture Monitoring and Decision Support System</p>
</header>

<main>
    <div class="notice">
        <strong>Demonstration mode:</strong>
        sensor values are simulated on your computer, not collected from a real field.
    </div>

    <section class="cards">
        <div class="card">
            <h3>Soil Moisture</h3>
            <div class="value" id="moisture">--</div>
            <p>Simulated percentage</p>
        </div>
        <div class="card">
            <h3>Temperature</h3>
            <div class="value" id="temperature">--</div>
            <p>Degrees Celsius</p>
        </div>
        <div class="card">
            <h3>Humidity</h3>
            <div class="value" id="humidity">--</div>
            <p>Simulated percentage</p>
        </div>
    </section>

    <section class="panel">
        <h2>Monitoring and Analysis</h2>
        <p><strong>Latest recommendation:</strong> <span id="recommendation">Generate a reading to begin.</span></p>
        <p><strong>Latest timestamp:</strong> <span id="timestamp">--</span></p>

        <div class="buttons">
            <button id="generateBtn" onclick="generateReading()">Generate and Save Reading</button>
            <button class="secondary" onclick="analyzeLatest()">Analyze Latest Reading</button>
            <a class="button-link" href="/api/export">Export CSV</a>
            <button class="optional" onclick="uploadToS3()">Optional: Upload to S3</button>
        </div>

        <div id="status" role="status">Ready.</div>
    </section>

    <section class="panel">
        <h2>Recent Sensor History</h2>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Soil Moisture</th>
                        <th>Temperature</th>
                        <th>Humidity</th>
                        <th>Recommendation</th>
                        <th>Timestamp</th>
                    </tr>
                </thead>
                <tbody id="history">
                    <tr><td colspan="6">Loading readings...</td></tr>
                </tbody>
            </table>
        </div>
    </section>
</main>

<footer>
    Student project demonstration · Flask · SQLite · Lambda-compatible analysis · Optional S3
</footer>

<script>
function showStatus(message) {
    document.getElementById("status").textContent = message;
}

function updateLatest(reading) {
    document.getElementById("moisture").textContent =
        reading.soil_moisture + "%";
    document.getElementById("temperature").textContent =
        reading.temperature + " °C";
    document.getElementById("humidity").textContent =
        reading.humidity + "%";
    document.getElementById("recommendation").textContent =
        reading.recommendation;
    document.getElementById("timestamp").textContent =
        reading.timestamp;
}

async function loadHistory() {
    try {
        const response = await fetch("/api/history");
        const data = await response.json();

        if (!response.ok) throw new Error(data.error || "Could not load history.");

        const body = document.getElementById("history");
        body.innerHTML = "";

        if (data.length === 0) {
            body.innerHTML = '<tr><td colspan="6">No readings yet. Generate one above.</td></tr>';
            return;
        }

        updateLatest(data[0]);

        for (const reading of data) {
            const tr = document.createElement("tr");
            const values = [
                reading.id,
                reading.soil_moisture + "%",
                reading.temperature + " °C",
                reading.humidity + "%",
                reading.recommendation,
                reading.timestamp
            ];

            for (const value of values) {
                const td = document.createElement("td");
                td.textContent = value;
                tr.appendChild(td);
            }
            body.appendChild(tr);
        }
    } catch (error) {
        showStatus("History error: " + error.message);
    }
}

async function generateReading() {
    const button = document.getElementById("generateBtn");
    button.disabled = true;
    showStatus("Generating and saving a simulated reading...");

    try {
        const response = await fetch("/api/readings", { method: "POST" });
        const data = await response.json();

        if (!response.ok) throw new Error(data.error || "Could not generate reading.");

        updateLatest(data);
        await loadHistory();
        showStatus("Reading generated and saved successfully.");
    } catch (error) {
        showStatus("Error: " + error.message);
    } finally {
        button.disabled = false;
    }
}

async function analyzeLatest() {
    showStatus("Analyzing the latest saved reading...");

    try {
        const response = await fetch("/api/analyze");
        const data = await response.json();

        if (!response.ok) throw new Error(data.error || "Analysis failed.");

        const result = data.analysis;
        document.getElementById("recommendation").textContent =
            result.recommendation;
        showStatus("Analysis completed locally using the Lambda-compatible function.");
    } catch (error) {
        showStatus("Analysis error: " + error.message);
    }
}

async function uploadToS3() {
    if (!confirm("Attempt an S3 upload? This requires a configured bucket and AWS credentials, and AWS usage may incur charges. Continue?")) {
        return;
    }

    showStatus("Checking S3 configuration and attempting upload...");

    try {
        const response = await fetch("/api/upload-to-s3", { method: "POST" });
        const data = await response.json();

        if (!response.ok) throw new Error(data.message || data.error || "Upload failed.");

        showStatus(data.message + " Bucket: " + data.bucket);
    } catch (error) {
        showStatus("S3 not available: " + error.message);
    }
}

loadHistory();
</script>
</body>
</html>
"""


@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD)


@app.route("/api/readings", methods=["POST"])
def create_reading():
    return jsonify(generate_sensor_reading())


@app.route("/api/history")
def get_history():
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT id, soil_moisture, temperature, humidity,
                   recommendation, timestamp
            FROM sensor_readings
            ORDER BY id DESC
            LIMIT 10
        """).fetchall()

    return jsonify([dict(row) for row in rows])


@app.route("/api/analyze")
def analyze_latest_reading():
    with get_connection() as connection:
        row = connection.execute("""
            SELECT soil_moisture, temperature, humidity
            FROM sensor_readings
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()

    if row is None:
        return jsonify({
            "error": "No readings found. Generate a reading first."
        }), 404

    analysis = analyze_values(
        row["soil_moisture"],
        row["temperature"],
        row["humidity"]
    )

    return jsonify({
        "source": "local Lambda-compatible function",
        "analysis": analysis
    })


@app.route("/api/export")
def export_readings():
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT id, soil_moisture, temperature, humidity,
                   recommendation, timestamp
            FROM sensor_readings
            ORDER BY id DESC
        """).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "id", "soil_moisture", "temperature",
        "humidity", "recommendation", "timestamp"
    ])

    for row in rows:
        writer.writerow([
            row["id"], row["soil_moisture"], row["temperature"],
            row["humidity"], row["recommendation"], row["timestamp"]
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                "attachment; filename=sensor_readings.csv"
        }
    )


@app.route("/api/upload-to-s3", methods=["POST"])
def upload_to_s3():
    bucket_name = os.environ.get("SMART_AGRICULTURE_S3_BUCKET")

    if not bucket_name:
        return jsonify({
            "error": "S3 is not configured.",
            "message": "No S3 bucket is configured. No upload was attempted."
        }), 400

    with get_connection() as connection:
        rows = connection.execute("""
            SELECT id, soil_moisture, temperature, humidity,
                   recommendation, timestamp
            FROM sensor_readings
            ORDER BY id DESC
        """).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "soil_moisture", "temperature",
        "humidity", "recommendation", "timestamp"
    ])

    for row in rows:
        writer.writerow([
            row["id"], row["soil_moisture"], row["temperature"],
            row["humidity"], row["recommendation"], row["timestamp"]
        ])

    try:
        s3 = boto3.client(
            "s3",
            region_name=os.environ.get(
                "AWS_DEFAULT_REGION", "eu-central-1"
            )
        )

        s3.put_object(
            Bucket=bucket_name,
            Key="sensor_readings.csv",
            Body=output.getvalue().encode("utf-8"),
            ContentType="text/csv"
        )

        return jsonify({
            "message": "CSV uploaded successfully.",
            "bucket": bucket_name,
            "file": "sensor_readings.csv"
        })

    except Exception:
        app.logger.exception("S3 upload failed")
        return jsonify({
            "error": "Upload failed. Check AWS credentials, bucket name, region, and permissions."
        }), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


initialize_database()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
