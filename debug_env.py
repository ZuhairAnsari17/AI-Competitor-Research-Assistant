#!/usr/bin/env python3
"""Debug script to verify .env loading and DagsHub setup."""

import os
import sys
from pathlib import Path

# Add repo to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("DEBUG: Environment & DagsHub Setup Verification")
print("=" * 80)

# Check if .env file exists
env_path = Path(".env")
print(f"\n1. .env file exists: {env_path.exists()}")
if env_path.exists():
    print(f"   Path: {env_path.absolute()}")
    print(f"   Size: {env_path.stat().st_size} bytes")

# Load settings via Pydantic
print("\n2. Loading settings via Pydantic BaseSettings...")
from app.core.config import get_settings

settings = get_settings()
print(f"   ✓ Settings loaded successfully")

# Check DagsHub credentials
print("\n3. DagsHub Credentials:")
dagshub_username = settings.dagshub_username.strip()
dagshub_repo_name = settings.dagshub_repo_name.strip()
dagshub_token = settings.dagshub_token.strip()

print(f"   DAGSHUB_USERNAME:  {dagshub_username if dagshub_username else '(empty)'}")
print(f"   DAGSHUB_REPO_NAME: {dagshub_repo_name if dagshub_repo_name else '(empty)'}")
print(f"   DAGSHUB_TOKEN:     {dagshub_token[:10]}...{dagshub_token[-5:] if dagshub_token else '(empty)'}")

all_set = all([dagshub_username, dagshub_repo_name, dagshub_token])
print(f"\n   All credentials present: {all_set}")

if not all_set:
    print("\n   ⚠️  ERROR: DagsHub credentials incomplete!")
    sys.exit(1)

# Check other settings
print("\n4. Other API Keys:")
print(f"   GROQ_API_KEY:      {settings.groq_api_key[:10] if settings.groq_api_key else '(empty)'}...")
print(f"   YOUTUBE_API_KEY:   {settings.youtube_api_key[:10] if settings.youtube_api_key else '(empty)'}...")

# Check if mlflow/dagshub are installed
print("\n5. Package Availability:")
try:
    import mlflow
    print(f"   ✓ mlflow {mlflow.__version__} installed")
except ImportError as e:
    print(f"   ✗ mlflow NOT installed: {e}")
    sys.exit(1)

try:
    import dagshub
    print(f"   ✓ dagshub installed")
except ImportError as e:
    print(f"   ✗ dagshub NOT installed: {e}")
    sys.exit(1)

# Try to initialize DagsHub
print("\n6. Testing DagsHub Initialization:")
try:
    dagshub.auth.add_app_token(token=dagshub_token)
    print(f"   ✓ DagsHub token authenticated")
    
    dagshub.init(
        repo_owner=dagshub_username,
        repo_name=dagshub_repo_name,
        mlflow=True,
    )
    print(f"   ✓ DagsHub initialized")
    
    tracking_uri = mlflow.get_tracking_uri()
    print(f"   ✓ MLflow tracking URI: {tracking_uri}")
    
    # Try to create/set experiment
    exp_name = settings.mlflow_experiment or "competitor-intelligence"
    experiment = mlflow.set_experiment(exp_name)
    print(f"   ✓ MLflow experiment '{exp_name}' set (id={experiment.experiment_id})")
    
except Exception as e:
    print(f"   ✗ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("✅ All checks passed! DagsHub is ready to use.")
print("=" * 80)
