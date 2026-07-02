# Smart Irrigation & Fertigation — Distributed Systems Architecture

> A distributed architecture for automated irrigation and fertigation management in open-field agriculture, designed as part of the Distributed Systems course at the University of Messina.

---

## Overview

Open-field agriculture is inherently distributed — sensors, actuators, and decision points are spread across hundreds or thousands of square meters. This project designs a **four-layer distributed system** that matches that physical reality: local edge nodes react in milliseconds, fog gateways buffer and aggregate, and a cloud layer runs AI-driven optimization.

The focus is on **architectural design and communication specification**, validated through a minimal proof of concept demonstrating gRPC communication between a simulated fog node and cloud server.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│         Layer 4 — Cloud / Centralized        │
│   AI models · gRPC Server · Historical DB    │
│          (IaaS VM — OpenStack)               │
└──────────────────┬──────────────────────────┘
                   │  gRPC + Protocol Buffers (WAN)
┌──────────────────┴──────────────────────────┐
│            Layer 3 — Fog Gateway             │
│  Aggregation · Local rules · Data buffering  │
│         (Raspberry Pi / Linux SBC)           │
└──────────────────┬──────────────────────────┘
                   │  MQTT / JSON over WiFi
┌──────────────────┴──────────────────────────┐
│             Layer 2 — Edge Node              │
│  Sensor reading · Filtering · Threshold rules│
│            (ESP32 / STM32)                   │
└──────────────────┬──────────────────────────┘
                   │  ZigBee / UART / I2C
┌──────────────────┴──────────────────────────┐
│        Layer 1 — Sensing & Actuation         │
│  Soil sensors · Electro-valves · Pumps       │
│           (Physical field devices)           │
└─────────────────────────────────────────────┘
```

**Key design principle:** Intelligence is graduated — the further from the field, the more computational power and the more complex the reasoning.

---

## Field Zones

| Zone | Crop Type | Irrigation Pattern |
|------|-----------|--------------------|
| A | Fruit Trees | Infrequent, high-volume |
| B | Vegetables | Frequent, low-volume |
| C | Seasonal Crops | Adaptive, context-dependent |

---

## Communication Model

| Link | Protocol | Reason |
|------|----------|--------|
| Layer 1 → 2 | ZigBee / UART | Low-power, short-range, constrained devices |
| Layer 2 → 3 | MQTT over WiFi | Lightweight pub/sub, runs on microcontrollers |
| Layer 3 → 4 | gRPC + Protocol Buffers | Binary serialization, schema-defined, HTTP/2 |

> gRPC is used **exclusively** between Fog and Cloud. Edge nodes lack the RAM and network stack required for HTTP/2.

---

## gRPC Service Definition

```protobuf
service FieldCoordinator {
  rpc SendSensorData     (SensorReading)     returns (Ack);
  rpc TriggerIrrigation  (ActuationCommand)  returns (ActuationResponse);
  rpc GetOptimizationPlan(ZoneRequest)       returns (IrrigationPlan);
}

message SensorReading {
  string zone_id       = 1;
  float  soil_moisture = 2;
  float  temperature   = 3;
  float  humidity      = 4;
  float  soil_ph       = 5;
  int64  timestamp     = 6;
}

message ActuationCommand {
  string zone_id          = 1;
  string action_type      = 2;  // "IRRIGATE" or "FERTIGATE"
  float  duration_minutes = 3;
  float  nutrient_dose_ml = 4;
}
```

---

## Operational Workflows

### 1 — Periodic Monitoring
```
Sensor (every 60s) → Edge (filter + 5-min average) → Fog (aggregate) → Cloud (store + update model)
```

### 2 — Emergency Local Response
```
Moisture < 25% → Edge opens valve immediately (10 min)
             → Reports to Fog → Cloud evaluates and may update plan
```

### 3 — AI Optimization (every 6 hours)
```
Cloud ingests all zone data → ML model forecasts demand →
Fertigation optimizer computes N/P/K doses →
Plans distributed down: Cloud → Fog → Edge → Actuators
```

### 4 — Feedback Loop
```
Actuator executes → Flow meter confirms → Edge → Fog → Cloud
(ground truth for AI model retraining)
```

---

## System Requirements

### Functional
| ID | Requirement |
|----|-------------|
| FR1 | Continuous environmental data acquisition across all zones |
| FR2 | Local aggregation, filtering, and anomaly detection at the edge |
| FR3 | Local rule-based decisions for time-critical actions without cloud dependency |
| FR4 | AI-based irrigation forecasting and fertigation dose optimization at the cloud |
| FR5 | Remote actuation control via well-defined RPC interfaces |
| FR6 | Coordinated state consistency across all distributed components |

### Non-Functional
| ID | Requirement |
|----|-------------|
| NFR1 | Scalability — new zones/nodes require no changes to existing components |
| NFR2 | Fault tolerance — degraded-mode operation at every layer |
| NFR3 | Low latency — emergency triggers execute within seconds |
| NFR4 | Modularity — versioned `.proto` interfaces enable independent evolution |
| NFR5 | Security — TLS + token auth on Fog↔Cloud; message validation on Edge↔Fog |
| NFR6 | Resource awareness — processing complexity increases with each layer upward |

---

## Fault Tolerance

| Failure | System Behavior |
|---------|-----------------|
| Cloud unreachable | Fog operates on cached rules; buffers data for later sync |
| Fog node down | Edge continues with local threshold-based control |
| Single edge failure | Only that zone is affected; all others continue normally |
| Sensor malfunction | Edge detects anomaly, flags it, excludes reading from forwarding |

**Priority: crop safety over optimization — always.**

---

## AI Modules (Cloud Layer)

**Irrigation Demand Forecasting**
- Model: Gradient Boosting or LSTM
- Input: historical soil moisture + weather forecast + crop growth stage
- Output: predicted water demand per zone for next 12–24 hours
- Result: up to 30% reduction in reactive irrigation

**Fertigation Dose Optimizer**
- Input: soil EC, pH, crop growth stage
- Output: N/P/K concentrate ratios + injection duration per cycle

---

## Proof of Concept

The PoC validates the Fog–Cloud gRPC interface using two independent Python processes.

**Fog Simulator (gRPC Client)** — generates synthetic sensor data and sends actuation requests.

**Cloud Server (gRPC Server)** — receives data, applies rule-based checks, returns structured responses.

### Validated
- gRPC client–server communication between independent processes
- Protocol Buffer serialization/deserialization without data loss
- `SendSensorData` and `TriggerIrrigation` RPC calls
- Extensibility: new RPC methods require only a `.proto` update

### Out of Scope (future work)
- Real sensor hardware and physical actuators
- AI model training and inference
- TLS security between Fog and Cloud
- Persistent database at the cloud layer
- Multi-zone concurrent load testing

---

## Infrastructure

The cloud layer is deployed on an **IaaS** virtual machine (e.g., OpenStack), providing:
- Elastic CPU/RAM scaling as the number of monitored zones grows
- Always-on availability independent of local farm network conditions
- Centralized storage for cross-zone historical analysis

---

## Project Info

| | |
|-|-|
| **Course** | Distributed Systems |
| **University** | University of Messina |
| **Professor** | Antonio Puliafito |
| **Teaching Assistant** | Giuseppe Tricomi |
| **Student** | Amirreza Soheiliarasi |
| **Student ID** | 574946 |
