"""Emit 'size key' lines for the ds007554 EEG/ECG/push-button files from the OpenNeuro S3 listing."""
import re, sys, urllib.request, urllib.parse
B = "https://s3.amazonaws.com/openneuro.org/?list-type=2&prefix=ds007554/&max-keys=1000"
tok = None
while True:
    u = B + (("&continuation-token=" + urllib.parse.quote(tok, safe="")) if tok else "")
    r = urllib.request.urlopen(u, timeout=60).read().decode()
    for k, s in re.findall(r"<Key>([^<]*)</Key>.*?<Size>(\d+)</Size>", r):
        if re.search(r"ds007554/(sub-\d+/ses-\d+/(eeg/|beh/.*(ECG|pushbutton))|[^/]+$|phenotype/)", k):
            print(s, k)
    m = re.search(r"<NextContinuationToken>([^<]*)", r)
    if not m: break
    tok = m.group(1)
