import boto3

client = boto3.client("rekognition", region_name="us-east-1")

print("Client created")

response = client.list_collections()
print("Rekognition works")
