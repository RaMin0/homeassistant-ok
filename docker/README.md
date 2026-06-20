# Local Home Assistant Docker Environment

This environment runs Home Assistant `2025.12.5` with the local OK custom component mounted
directly into `/config/custom_components/ok`.

The mounted Home Assistant config directory is runtime state and is ignored by git:

- `docker/ha/config`

Start Home Assistant:

```bash
docker compose up -d homeassistant
```

Open:

```text
http://localhost:8123
```

The compose file binds Home Assistant to `127.0.0.1:8123`, so the development instance is only
reachable from the local machine by default.

Start with automatic restarts when `custom_components/ok` changes:

```bash
docker compose --profile watch up -d homeassistant watcher
```

The bind mount makes file changes visible inside the container immediately. Home Assistant
does not reliably hot-reload Python code from custom components, so the watcher service restarts
the selected Home Assistant container automatically after source changes. That avoids manual
container restarts while still running the selected Home Assistant version.

The watcher profile mounts `/var/run/docker.sock` so it can restart the Home Assistant
container. Use it only on a trusted development machine.

Follow logs:

```bash
docker compose logs -f homeassistant
```

Stop the environment:

```bash
docker compose down
```

Remove the local Home Assistant runtime state:

```bash
docker compose down
rm -rf docker/ha/config
```

Installed HACS/custom cards and generated frontend files live under `docker/ha/config` as
runtime state. Keep that state local; it is ignored by the repository.
