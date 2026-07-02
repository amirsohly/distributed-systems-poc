"""
Fog Node Simulator — Layer 3
==============================
Simulates a fog gateway acting as a gRPC client toward the Cloud server.

In a real deployment this process would:
  - receive aggregated data packets from edge nodes via MQTT
  - buffer them locally when cloud connectivity is unavailable
  - forward batched readings to the cloud via gRPC
  - relay actuation commands back down to edge nodes

For the PoC, it generates synthetic sensor readings and demonstrates
all three RPC calls defined in field_coordinator.proto.

Run (after starting coordination_server.py):
    python fog_simulator.py

Dependencies:
    pip install grpcio grpcio-tools
    python -m grpc_tools.protoc -I../proto --python_out=. \
        --grpc_python_out=. ../proto/field_coordinator.proto
"""

import grpc
import time
import random
import logging
from datetime import datetime, timezone

import field_coordinator_pb2 as pb2
import field_coordinator_pb2_grpc as pb2_grpc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [FOG]   %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Zone definitions ─────────────────────────────────────────────────────────
# Each entry describes realistic baseline sensor ranges for that zone.
ZONES = {
    "zone_a": {
        "description":   "Fruit Trees — deep-rooted, infrequent irrigation",
        "moisture_range": (30.0, 60.0),
        "temp_range":     (18.0, 32.0),
        "humidity_range": (45.0, 75.0),
        "ph_range":       (6.0, 7.0),
        "ec_range":       (0.8, 1.5),
    },
    "zone_b": {
        "description":   "Vegetables — shallow-rooted, frequent irrigation",
        "moisture_range": (20.0, 50.0),
        "temp_range":     (17.0, 30.0),
        "humidity_range": (50.0, 80.0),
        "ph_range":       (5.8, 6.8),
        "ec_range":       (1.0, 2.0),
    },
    "zone_c": {
        "description":   "Seasonal Crops — adaptive strategy",
        "moisture_range": (25.0, 55.0),
        "temp_range":     (16.0, 33.0),
        "humidity_range": (40.0, 70.0),
        "ph_range":       (6.2, 7.2),
        "ec_range":       (0.6, 1.2),
    },
}

CLOUD_ADDRESS = "localhost:50051"
CRITICAL_MOISTURE = 25.0   # % VWC — threshold that triggers emergency irrigation


# ── Helpers ──────────────────────────────────────────────────────────────────

def synthetic_reading(zone_id: str) -> pb2.SensorReading:
    """Generate a plausible sensor reading for a zone."""
    cfg = ZONES[zone_id]
    return pb2.SensorReading(
        zone_id=zone_id,
        soil_moisture=round(random.uniform(*cfg["moisture_range"]), 2),
        temperature=round(random.uniform(*cfg["temp_range"]), 2),
        humidity=round(random.uniform(*cfg["humidity_range"]), 2),
        soil_ph=round(random.uniform(*cfg["ph_range"]), 2),
        soil_ec=round(random.uniform(*cfg["ec_range"]), 3),
        timestamp=int(time.time()),
    )


# ── Workflow A: periodic sensor data transmission ────────────────────────────

def workflow_sensor_data(stub: pb2_grpc.FieldCoordinatorStub) -> None:
    """Send one sensor reading per zone — simulates a 5-minute aggregation cycle."""
    log.info("─── Workflow A: Sending sensor data for all zones ───")

    for zone_id in ZONES:
        reading = synthetic_reading(zone_id)

        log.info(
            "Sending %-8s | moisture=%.1f%%  temp=%.1f°C  "
            "pH=%.1f  EC=%.3f  humidity=%.1f%%",
            zone_id,
            reading.soil_moisture,
            reading.temperature,
            reading.soil_ph,
            reading.soil_ec,
            reading.humidity,
        )

        try:
            ack = stub.SendSensorData(reading)
            log.info("  ← Server: [%s] %s", ack.status, ack.message)
        except grpc.RpcError as e:
            log.error("  ← gRPC error: %s — %s", e.code(), e.details())

        # Simulate fog batching interval
        time.sleep(0.3)


# ── Workflow B: emergency irrigation trigger ─────────────────────────────────

def workflow_emergency_irrigation(
    stub: pb2_grpc.FieldCoordinatorStub,
    zone_id: str = "zone_b",
) -> None:
    """
    Simulates what happens when an edge node detects critically low moisture
    and the fog node escalates to the cloud for confirmation.

    In a real system the fog node would also relay the command downward
    to the edge node immediately, without waiting for cloud confirmation.
    """
    log.info("─── Workflow B: Emergency irrigation trigger for %s ───", zone_id)

    command = pb2.ActuationCommand(
        zone_id=zone_id,
        action_type="IRRIGATE",
        duration_minutes=15.0,
        nutrient_dose_ml=0.0,
    )

    log.info(
        "Sending IRRIGATE command | zone=%s  duration=%.1f min",
        zone_id, command.duration_minutes,
    )

    try:
        response = stub.TriggerIrrigation(command)
        log.info(
            "  ← Server: confirmed=%s  start=%s  msg=%s",
            response.confirmed,
            response.scheduled_start,
            response.message,
        )
    except grpc.RpcError as e:
        log.error("  ← gRPC error: %s — %s", e.code(), e.details())


# ── Workflow C: fertigation command ─────────────────────────────────────────

def workflow_fertigation(
    stub: pb2_grpc.FieldCoordinatorStub,
    zone_id: str = "zone_b",
) -> None:
    """Request a fertigation cycle for a zone."""
    log.info("─── Workflow C: Fertigation trigger for %s ───", zone_id)

    command = pb2.ActuationCommand(
        zone_id=zone_id,
        action_type="FERTIGATE",
        duration_minutes=10.0,
        nutrient_dose_ml=50.0,
    )

    log.info(
        "Sending FERTIGATE command | zone=%s  duration=%.1f min  dose=%.1f ml",
        zone_id, command.duration_minutes, command.nutrient_dose_ml,
    )

    try:
        response = stub.TriggerIrrigation(command)
        log.info(
            "  ← Server: confirmed=%s  start=%s  msg=%s",
            response.confirmed,
            response.scheduled_start,
            response.message,
        )
    except grpc.RpcError as e:
        log.error("  ← gRPC error: %s — %s", e.code(), e.details())


# ── Workflow D: fetch AI optimization plan ───────────────────────────────────

def workflow_get_plan(stub: pb2_grpc.FieldCoordinatorStub) -> None:
    """Request the latest AI-generated plan for every zone."""
    log.info("─── Workflow D: Fetching optimization plans for all zones ───")

    for zone_id in ZONES:
        request = pb2.ZoneRequest(
            zone_id=zone_id,
            timestamp=int(time.time()),
        )

        try:
            plan = stub.GetOptimizationPlan(request)
            log.info(
                "  Plan for %-8s | start=%s  duration=%.1f min  "
                "action=%-10s  dose=%.1f ml  mix=%s",
                zone_id,
                plan.scheduled_start,
                plan.duration_minutes,
                plan.action_type,
                plan.nutrient_dose_ml,
                plan.nutrient_mix,
            )
        except grpc.RpcError as e:
            log.error("  ← gRPC error: %s — %s", e.code(), e.details())

        time.sleep(0.2)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("Fog Node Simulator starting — connecting to Cloud at %s", CLOUD_ADDRESS)

    # NOTE: In production, replace insecure_channel with:
    #   credentials = grpc.ssl_channel_credentials(root_certificates=...)
    #   channel = grpc.secure_channel(CLOUD_ADDRESS, credentials)
    with grpc.insecure_channel(CLOUD_ADDRESS) as channel:
        stub = pb2_grpc.FieldCoordinatorStub(channel)

        print()
        workflow_sensor_data(stub)
        print()
        workflow_emergency_irrigation(stub, zone_id="zone_b")
        print()
        workflow_fertigation(stub, zone_id="zone_b")
        print()
        workflow_get_plan(stub)
        print()

    log.info("Fog Node Simulator finished.")


if __name__ == "__main__":
    main()
