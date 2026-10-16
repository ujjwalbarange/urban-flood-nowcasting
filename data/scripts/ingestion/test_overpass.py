import urllib.request, urllib.parse, json

query = """[out:json][timeout:25];
(
  way["highway"~"motorway|trunk|primary"](18.89,72.77,19.34,73.04);
);
out tags count;
"""

endpoints = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
]

for ep in endpoints:
    try:
        req = urllib.request.Request(ep, data=urllib.parse.urlencode({'data': query}).encode('utf-8'), headers={'User-Agent': 'MUFNS/1.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            d = json.loads(resp.read().decode('utf-8'))
            print(ep, 'SUCCESS:', d.get('elements', [{}])[0])
            break
    except Exception as e:
        print(ep, 'FAILED:', e)
