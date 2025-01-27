import json

def clean_har(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        har_data = json.load(f)

    entries = har_data.get("log", {}).get("entries", [])
    cleaned_entries = []

    for entry in entries:
        request = entry.get("request", {})
        response = entry.get("response", {})
        cleaned_entry = {
            "url": request.get("url"),
            "method": request.get("method"),
            "headers": request.get("headers"),
            "queryString": request.get("queryString"),
            "postData": request.get("postData"),
            "status": response.get("status"),
            "statusText": response.get("statusText"),
            "time": entry.get("time"),
        }
        cleaned_entries.append(cleaned_entry)

    cleaned_har = {"log": {"entries": cleaned_entries}}

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_har, f, indent=2)

# Использование
clean_har(r"C:\Users\User\Downloads\2fa.har", "2fa.har")
