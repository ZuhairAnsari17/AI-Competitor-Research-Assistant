import os
import time
import logging
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

_mlflow_ready   = False
_experiment_id: Optional[str] = None

PROMPT_VERSION = "v2.0"


def setup_mlflow():
    global _mlflow_ready, _experiment_id
    username  = os.getenv("DAGSHUB_USERNAME", "").strip()
    repo_name = os.getenv("DAGSHUB_REPO_NAME", "").strip()
    token     = os.getenv("DAGSHUB_TOKEN", "").strip()
    exp_name  = os.getenv("MLFLOW_EXPERIMENT_NAME", "competitor-intelligence")

    if not all([username, repo_name, token]):
        logger.warning("DagsHub credentials missing — MLflow tracking disabled")
        return

    try:
        import mlflow
        import dagshub
        dagshub.auth.add_app_token(token=token)
        dagshub.init(repo_owner=username, repo_name=repo_name, mlflow=True)
        experiment    = mlflow.set_experiment(exp_name)
        _experiment_id = experiment.experiment_id
        _mlflow_ready  = True
        logger.info(f"MLflow + DagsHub ready — {mlflow.get_tracking_uri()} | experiment: {exp_name}")
    except ImportError as e:
        logger.warning(f"MLflow import failed: {e}")
    except Exception as e:
        logger.warning(f"MLflow setup failed: {e}")


@contextmanager
def track_agent_run(agent_name: str, competitor: str, extra_params: dict = None):
    start    = time.time()
    metrics  = {}
    _run_ctx = None

    if _mlflow_ready:
        try:
            import mlflow
            from app.core.config import get_config
            model    = get_config().get("apis", {}).get("groq", {}).get("model", "llama-3.3-70b-versatile")
            _run_ctx = mlflow.start_run(
                run_name=f"{agent_name}__{competitor}__{int(start)}",
                experiment_id=_experiment_id,
                tags={"agent": agent_name, "competitor": competitor,
                      "mlflow.runName": f"{agent_name} · {competitor}"},
            )
            _run_ctx.__enter__()
            params = {"agent": agent_name, "competitor": competitor, "model": model,
                      "prompt_version": PROMPT_VERSION}
            if extra_params:
                params.update({k: str(v)[:250] for k, v in extra_params.items()})
            mlflow.log_params(params)
        except Exception as e:
            logger.debug(f"MLflow run open failed: {e}")
            _run_ctx = None

    try:
        yield metrics
    finally:
        elapsed_ms = round((time.time() - start) * 1000, 2)
        metrics.setdefault("agent_latency_ms", elapsed_ms)

        if _run_ctx is not None:
            try:
                import mlflow
                for k, v in metrics.items():
                    if isinstance(v, (int, float)):
                        mlflow.log_metric(k, float(v))
                    elif isinstance(v, str) and v:
                        mlflow.set_tag(k, v[:250])
                mlflow.set_tag("run_status", "FAILED" if metrics.get("error") else "FINISHED")
                _run_ctx.__exit__(None, None, None)
            except Exception as e:
                logger.debug(f"MLflow flush failed: {e}")
                try:
                    _run_ctx.__exit__(None, None, None)
                except Exception:
                    pass
