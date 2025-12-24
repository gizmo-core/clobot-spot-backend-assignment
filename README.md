# KLOBOT SPOT Backend Assignment (MQTT → Validate → Store → Stream)

본 과제는 다수 로봇의 상태 메시지를 **MQTT(v5)** 로 수신하고, 명세 기반 **유효성 검증(Validation)** 후 **PostgreSQL** 에 저장하며,  
특정 로봇의 상태 변화를 **SSE(Server-Sent Events)** 로 실시간 스트리밍하고 **이력 조회 API** 를 제공하는 백엔드 서비스를 구현합니다.

---

## 🏗️ Architecture

```mermaid
flowchart TD
    classDef edge fill:#f9f9f9,stroke:#333,stroke-width:2px;
    classDef infra fill:#e1f5fe,stroke:#0277bd,stroke-width:2px;
    classDef app fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;
    classDef client fill:#fff3e0,stroke:#ef6c00,stroke-width:2px;

    subgraph IoT_Layer ["IoT Edge Layer"]
        MockRobot[Mock Robot Generator]:::edge
    end

    subgraph Infrastructure ["Infrastructure (Docker)"]
        Mosquitto["MQTT Broker<br/>(Eclipse Mosquitto)"]:::infra
        Postgres[("PostgreSQL<br/>Robot Status History")]:::infra
    end

    subgraph Backend ["FastAPI Application (Async)"]
        subgraph Worker ["Background Tasks"]
            MQTT_Sub["MQTT Subscriber<br/>(aiomqtt)"]:::app
            Validator["Data Validator<br/>(Pydantic)"]:::app
        end
        
        subgraph API ["API Service"]
            StreamMgr["SSE Connection Manager<br/>(Per-Robot Fan-out)"]:::app
            HistoryAPI["History REST API"]:::app
        end
    end

    subgraph Client ["Client"]
        SSEClient["SSE Client<br/>(Browser / curl)"]:::client
    end

    MockRobot --"1. Publish (topic: robot/+/status)"--> Mosquitto
    Mosquitto --"2. Subscribe (async)"--> MQTT_Sub
    
    MQTT_Sub --> Validator
    Validator --"3-A. Insert valid data"--> Postgres
    Validator --"3-B. Broadcast event"--> StreamMgr
    
    StreamMgr --"4. Stream updates (SSE)"--> SSEClient
    SSEClient --"5. Query history"--> HistoryAPI
    HistoryAPI --"6. Select by time range"--> Postgres
````

---

## ✅ Tech Stack

* **Python / FastAPI**: `async/await` 기반 I/O 처리에 적합하며, Pydantic으로 명세 기반 검증을 명확하게 구현
* **MQTT v5**: 로봇/IoT 상태 수집에 적합한 pub/sub 프로토콜 (Topic 기반 라우팅)
* **SSE**: 서버 → 클라이언트 단방향 실시간 스트리밍에 적합하며 구현이 단순
* **PostgreSQL**: 구조화된 상태 이력 데이터를 스키마로 안정적으로 관리하고, `(robot, time)` 인덱스 기반 조회가 용이
  * 선정 이유: 시계열 조회 패턴에 강하고, 확장(예: TimescaleDB/PostGIS)으로 향후 요구에 대응 가능

  * (옵션) 추후 시계열/공간 확장(TimescaleDB/PostGIS)도 고려 가능

---

## 🚀 How to Run

> 아래 예시는 `docker-compose` 기반 실행을 가정합니다.
> (프로젝트에 맞게 경로/파일명을 조정해 주세요.)

1. **Run infrastructure**

   ```bash
   docker-compose up -d
   ```

2. **Install deps**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Set environment**

   ```bash
   export DATABASE_URL="postgresql+asyncpg://spot:spotpw@localhost:5432/spotdb"
   export MQTT_HOST="localhost"
   export MQTT_PORT="21883"
   export MQTT_USERNAME="test"
   export MQTT_PASSWORD="test1234"
   ```

4. **Run FastAPI**

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Run Mock publisher (local)**

   ```bash
   python -m app.mock.publisher
   ```

6. **Run Mock publisher (docker compose)**

   ```bash
   docker-compose up -d publisher
   ```

---

## 🔌 MQTT

* **Broker**

  * Host: `localhost`
  * Port: `21883`
  * Username/Password: `test` / `test1234`
  * Docker compose 내부: Host `mqtt`, Port `1883`

* **Topic**

  * Publish: `robot/{SERIAL_NUMBER}/status`
  * Subscribe: `robot/+/status` ( `+` 는 단일 토픽 레벨 와일드카드)

---

## 🌊 APIs

### 1) Real-time feed (SSE)

* `GET /robots/{serial_number}/feed`

**Example**

```bash
curl -N http://localhost:8000/robots/ROBOT-001/feed
```

### 2) History query

* `GET /robots/{serial_number}/history?start_time=...&end_time=...`
* `include_payload=true` 로 원문 payload 포함 (선택)
* `limit` 으로 최대 반환 수 제한 (default: 500, max: 5000)

**Example**

```bash
curl "http://localhost:8000/robots/ROBOT-001/history?start_time=2025-12-01T00:00:00Z&end_time=2025-12-01T01:00:00Z"
```

---

## ✅ Data Validation Rules

MQTT로 수신한 로봇 상태 메시지는 아래 조건을 만족할 때만 DB에 저장되고 SSE로 전파됩니다.

* **battery_level**

  * `1 ~ 100` 범위의 정수
* **battery_status**

  * `CHARGING` 또는 `DISCHARGING`
* **driving_status**

  * `IDLE` 또는 `MOVING`
* **current_drive_id**

  * `driving_status == MOVING` 인 경우 **UUID 필수**
  * `driving_status == IDLE` 인 경우 **null/없음**
* **location**

  * `latitude`, `longitude`, `height` 3개 필드가 모두 존재해야 함 (float)
* **timestamp**

  * 입력 필드명은 `timestamp`
  * DB에는 `ts`로 저장, 누락 시 수신 시각 사용

> Validation 실패 메시지는 저장하지 않으며, 운영 관점에서 원인 파악을 위해 구조화 로그로 남기는 것을 권장합니다.

---

## 🧩 Design Notes / Assumptions

* MQTT Subscriber는 FastAPI 앱 구동 시 백그라운드 태스크로 실행된다고 가정합니다.
* SSE는 로봇별로 fan-out 가능한 구조(로봇별 연결 관리)를 목표로 합니다.
* 본 과제 범위에서는 **정확성(Validation) / 실시간성(SSE) / 조회성(History)** 을 우선합니다.

---

## 🤖 Mock Publisher

Publisher는 단일 프로세스에서 여러 로봇을 시뮬레이션합니다.

**Environment variables**

* `ROBOT_COUNT` (default: 2)
* `PUBLISH_INTERVAL_SEC` (default: 1.0, per-robot interval)
* `INVALID_RATE` (default: 0.0)
* `JITTER_MAX_SEC` (default: 0.2)
* `ENABLE_STATS_LOG` (default: false)
* `STATS_LOG_INTERVAL_SEC` (default: 5.0)

---

## 🧪 Tests

```bash
pytest
```

---

## 🔭 Next Steps (Optional)

* Idempotency (중복 수신 시 처리 정책)
* Retry / Backoff (MQTT 재연결 및 DB 오류 대응)
* Observability (Prometheus metrics + Grafana dashboard)
* Load test & indexing strategy refinement
