import os
import json
import boto3

def load_aws_secrets():
    try:
        client = boto3.client(
            "secretsmanager",
            region_name="ap-south-1"
        )

        response = client.get_secret_value(
            SecretId="ai-competitor-secrets"
        )

        secrets = json.loads(response["SecretString"])

        for key, value in secrets.items():
            os.environ[key] = value

        print("AWS secrets loaded")

    except Exception as e:
        print("Failed to load AWS secrets:", e)
