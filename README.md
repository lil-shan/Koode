
# Koode + Parayu  
AI-Powered Hospital Intake System (Edge AI for Public Healthcare, Kerala)

Source document: koode_parayu.docx

---

## Overview

Koode + Parayu is a fully offline, edge AI-based hospital intake and navigation system designed for high-volume government hospitals.

- Parayu → AI-powered symptom intake kiosk (voice-first, Malayalam supported)  
- Koode Bot → ESP32-based robot for patient navigation  

The system replaces manual reception workflows with structured AI-driven triage.

---

## Problem Statement

Government hospitals face severe intake bottlenecks:

- Overloaded reception staff handling hundreds of patients  
- No structured triage → incorrect department routing  
- No symptom history passed to doctors  
- Elderly patients struggle with navigation  
- No epidemic pattern detection  

This is primarily a workflow inefficiency problem.

---

## Solution Architecture

### Components

| Component        | Function                          |
|-----------------|----------------------------------|
| Parayu Kiosk    | AI-based symptom intake          |
| Koode Bot       | Physical patient navigation      |
| Doctor Dashboard| Pre-consult clinical summaries   |
| SQLite DB       | Patient records + analytics      |
| MQTT Broker     | Communication layer              |

---

## Key Features

- Fully offline operation (no cloud dependency)  
- Malayalam, Hindi, English voice intake  
- Structured AI-driven clinical interview  
- Automatic department assignment  
- Real-time doctor dashboard  
- ESP32 robot navigation via MQTT  
- Symptom aggregation for epidemic detection  
- Privacy-first architecture  

---

## AI Stack

### Models

| Model                          | Role                         |
|--------------------------------|------------------------------|
| Gemma 4 E2B (Q4_K_M)           | Clinical reasoning + reports |
| Whisper (faster-whisper small) | Speech-to-text               |
| RAG System                     | Context injection            |

### Why Gemma 4

- Native Malayalam support  
- Strong instruction following  
- Apache 2.0 license  
- Optimized for edge devices  
- Runs on Raspberry Pi 5  

---

## System Flow


Patient → Kiosk → Speech Input → Whisper STT
→ RAG Context → Gemma 4 (Interview)
→ Clinical JSON → SQLite + MQTT
→ Koode Bot Navigation
→ Doctor Dashboard



---

## Hardware

### Parayu Kiosk

- Raspberry Pi 5 (8GB)  
- Touchscreen display  
- USB microphone  
- Speaker (optional)  
- Thermal printer  
- Hailo-8 AI HAT (optional)  

### Koode Bot

- ESP32-S3  
- HC-SR04 ultrasonic sensors (x4)  
- L298N motor driver  
- DC motors  
- RFID system  
- OLED display  
- I2S speaker  
- LiPo battery  

---

## Performance Metrics

| Metric                     | Value        |
|--------------------------|-------------|
| Model load time          | ~35 sec     |
| Response latency         | 10–30 sec   |
| STT latency              | 2–6 sec     |
| Report generation        | 60–120 sec  |
| MQTT latency             | <1 sec      |
| RAM usage                | ~9GB        |

---

## Limitations

- High inference latency  
- Malayalam STT accuracy varies  
- Some department misclassification (~15%)  
- No authentication layer  
- Epidemic dashboard incomplete  

---

## Real-World Impact

### Beneficiaries

- Patients → faster intake  
- Doctors → pre-consult summaries  
- Staff → reduced workload  
- Public health → outbreak detection  

### Deployment Targets

- Government hospitals  
- Primary Health Centres  
- High-volume OPDs  

---

## Setup Guide

### System Setup

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install ffmpeg mosquitto mosquitto-clients python3-venv -y
````

### Start MQTT

```bash
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

### Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma4:e2b-it-q4_K_M
```

### Python Environment

```bash
python3 -m venv ~/kiosk-env
source ~/kiosk-env/bin/activate

pip install flask flask-cors faster-whisper paho-mqtt requests
```

---

## Run

```bash
source ~/kiosk-env/bin/activate
cd ~/kiosk
python3 app.py
```

Access:

* Kiosk: http://PI_IP:5000
* Doctor dashboard: http://PI_IP:5000/doctor

---

## ESP32 Configuration

```cpp
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* mqtt_server = "192.168.x.x";
```

* Uses PubSubClient and ArduinoJson
* Subscribes to topic: koode/bot/navigate

---

## Design Decisions

| Decision        | Reason                          |
| --------------- | ------------------------------- |
| Offline-first   | Unreliable hospital internet    |
| LLM-based       | Handles natural language input  |
| RAG system      | Reduces prompt size and latency |
| RFID navigation | Simpler than vision-based SLAM  |

---

## Future Work

* NVMe SSD optimization
* Malayalam STT fine-tuning
* Streaming LLM responses
* Epidemic alert dashboard
* Aadhaar integration
* Secure communication (HTTPS, mTLS)
* Multi-kiosk deployment

---

## Privacy

* No cloud APIs
* No external data transfer
* Fully on-device inference

---

## License

To be added

---

## Tagline

Built with on-device AI. No cloud. No compromise on patient privacy.

```
```
