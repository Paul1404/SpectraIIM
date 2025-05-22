# SpectraIIM - ISP Internet Monitoring

**SpectraIIM** (ISP Internet Monitoring) is an open-source tool for logging and visualizing your internet connection’s health.

**⚠️ This project is a work in progress (WIP). Features and documentation may change.**

---

## Current Features

- **Continuous Monitoring**: Logs key network metrics (ping, jitter, packet loss, DNS resolution time, download/upload speeds) to a PostgreSQL database.
- **Grafana Integration**: Visualize your network logs in real time using Grafana dashboards.
- **Containerized Deployment**: Easily run the monitor, database, and Grafana with Docker Compose.
- **Persistent Storage**: All data and logs are stored in Docker volumes for durability.

---

## Planned Features

- **Automated Reports**: Exportable reports (PDF, CSV) based on logged data.
- **Customizable Alerts**: Notifications for high latency, downtime, or other threshold breaches.
- **User-friendly Setup**: Streamlined configuration and onboarding.
- **Data Privacy**: All monitoring data remains on your infrastructure.

---

## Installation

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed
- (Optional) [Docker Compose](https://docs.docker.com/compose/)

### Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Paul1404/SpectraIIM.git
   cd SpectraIIM
   ```

2. **Start the stack:**
   ```bash
   docker compose up -d
   ```

3. **Access Grafana:**
   - Open [http://localhost:3000](http://localhost:3000)
   - Login: `admin` / `admin`
   - Add the PostgreSQL data source (host: `postgres:5432`, db: `spectraiim`, user: `spectra`, password: `spectra_password`)
   - Create dashboards to visualize the `network_logs` table

---

## Configuration

All configuration is handled via environment variables in `docker-compose.yml`.
You can adjust monitoring intervals, database credentials, and more as needed.

---

## Contributing

Contributions are welcome! Please open issues or pull requests as you see fit.

---

## License

[MIT](LICENSE)

---

## Status

**This project is under active development and not yet feature complete. Use at your own risk.**