import time
from redis import Redis
from app.core.config import settings

def main():
    # Production worker boundary. Future asynchronous notification/escalation jobs
    # consume Redis streams here. Keeping it as a separate container makes the
    # local deployment topology match the later Kubernetes topology.
    r = Redis.from_url(settings.redis_url, decode_responses=True)
    while True:
        try:
            r.ping()
        except Exception:
            pass
        time.sleep(10)

if __name__ == "__main__":
    main()
