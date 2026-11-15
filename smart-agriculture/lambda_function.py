
import json
import math


def lambda_handler(event, context=None):
    """Analyze agricultural sensor readings using simple demo rules."""

    try:
        soil_moisture = float(event["soil_moisture"])
        temperature = float(event["temperature"])
        humidity = float(event["humidity"])
    except (KeyError, TypeError, ValueError):
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": (
                    "Provide soil_moisture, temperature, and humidity "
                    "as numeric values."
                )
            })
        }

    values = (soil_moisture, temperature, humidity)

    if not all(math.isfinite(value) for value in values):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Values must be finite numbers."})
        }

    if not 0 <= soil_moisture <= 100:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "Soil moisture must be between 0 and 100."
            })
        }

    if not 0 <= humidity <= 100:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "Humidity must be between 0 and 100."
            })
        }

    if soil_moisture < 30:
        recommendation = (
            "Low soil moisture: assess crop needs and irrigation."
        )
    elif soil_moisture < 45:
        recommendation = (
            "Soil moisture is moderate: continue monitoring."
        )
    else:
        recommendation = (
            "Soil moisture is adequate under this simple rule."
        )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "soil_moisture": soil_moisture,
            "temperature": temperature,
            "humidity": humidity,
            "recommendation": recommendation
        })
    }
