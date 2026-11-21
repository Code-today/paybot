import requests

requests.post(
    "http://localhost:5000/callback",
    json={"response": {"ExternalReference": "test-001", "Status": "Success"}},
)
print(requests.get("http://localhost:5000/status/test-001").json())