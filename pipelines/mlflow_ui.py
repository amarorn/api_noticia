import argparse
import subprocess

from config import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Sobe MLflow UI apontando para o tracking do projeto")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5001)
    args = parser.parse_args()
    cmd = [
        "mlflow",
        "ui",
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--backend-store-uri",
        settings.mlflow_tracking_uri,
    ]
    print("Iniciando:", " ".join(cmd))
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
